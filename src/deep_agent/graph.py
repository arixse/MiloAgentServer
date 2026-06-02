"""Deep Agent graph for deployment.

Agent 工厂模块 —— 按 thread_id 缓存 agent 实例，每个 thread 独占一个 sandbox。
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.store.mongodb import MongoDBStore
from pymongo import MongoClient

from deep_agent.opensandbox_backend import get_or_create_sandbox, cleanup_sandbox
from deep_agent.sub_agents import get_sub_agents
from model_provider import deepseek_model
from tools.file_tool import get_file_tools
from tools.install_skill import get_skill_tools
from tools.mcp_tool import get_mcp_tools
from tools.search_tool import get_search_tools
from utils.path import get_root_path

load_dotenv()

root_path = get_root_path()
skill_path = os.path.join(root_path, "skills")
print(f"skill_path: {skill_path}")
print(f"root_path: {root_path}")

# ---------------------------------------------------------------------------
# MongoDB / 持久化配置
# ---------------------------------------------------------------------------
USE_MONGO_PERSISTENCE = os.getenv("USE_MONGO_PERSISTENCE", "").lower() == "true"
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "MiloAgent")

_mongo_client: MongoClient | None = None


def _get_mongo_client() -> MongoClient:
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(MONGO_URI)
        print(f"[MongoDB] 已连接到 {MONGO_URI}")
    return _mongo_client


# ---------------------------------------------------------------------------
# Model & system prompt
# ---------------------------------------------------------------------------
DEFAULT_MODEL = deepseek_model
SYSTEM_PROMPT = """
You are a deep agent.

Workflow:
1. Write and maintain a todo list for non-trivial requests.
2. Delegate focused fact-finding to subagents when helpful.
3. Store intermediate drafts in files when the task is long.
4. Before finalizing, critique your work for risks, gaps, and missing constraints.
5. Return concise, actionable output.

- Prefer concrete evidence over assumptions.
- State unresolved uncertainty explicitly.
- Keep output compact unless the user asks for depth.
""".strip()


@tool
def utc_now() -> str:
    """Return the current UTC timestamp in ISO format."""
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Thread 持久化 —— Redis 存储线程元数据
# ---------------------------------------------------------------------------
import redis.asyncio as aioredis

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_THREAD_KEY_PREFIX = "milo_agent:thread"

_redis: aioredis.Redis | None = None


async def _get_redis() -> aioredis.Redis:
    """获取 Redis 异步客户端（单例）。"""
    global _redis
    if _redis is None:
        _redis = aioredis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True,
        )
    return _redis


def _thread_key(thread_id: str) -> str:
    return f"{REDIS_THREAD_KEY_PREFIX}:{thread_id}"


async def save_thread_meta(
    thread_id: str,
    user_id: str = "default_user",
    metadata: dict | None = None,
) -> None:
    """持久化线程元数据到 Redis。"""
    if not user_id:
        raise ValueError("user_id cannot be empty")
    r = await _get_redis()
    data: dict[str, str] = {
        "thread_id": thread_id,
        "user_id": user_id,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    if metadata:
        data["metadata"] = json.dumps(metadata, ensure_ascii=False)
    await r.hset(_thread_key(thread_id), mapping=data)


async def get_thread_meta(thread_id: str) -> dict | None:
    """从 Redis 读取线程元数据。"""
    r = await _get_redis()
    data = await r.hgetall(_thread_key(thread_id))
    return data if data else None


async def delete_thread_meta(thread_id: str) -> None:
    """从 Redis 删除线程元数据。"""
    r = await _get_redis()
    await r.delete(_thread_key(thread_id))


async def list_all_threads() -> list[dict]:
    """从 Redis 列出所有线程元数据（无用户过滤，管理用）。"""
    r = await _get_redis()
    keys = await r.keys(f"{REDIS_THREAD_KEY_PREFIX}:*")
    if not keys:
        return []
    results = []
    for key in keys:
        data = await r.hgetall(key)
        if data:
            results.append(data)
    # 按创建时间倒序
    results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return results


async def list_threads_by_user(user_id: str) -> list[dict]:
    """从 Redis 列出指定用户的所有线程元数据。"""
    all_threads = await list_all_threads()
    return [t for t in all_threads if t.get("user_id") == user_id]


# ---------------------------------------------------------------------------
# Agent 缓存 —— 每个 thread_id 独占一个 agent（及其 sandbox）
# ---------------------------------------------------------------------------
_agent_cache: dict[str, Any] = {}
_agent_lock = asyncio.Lock()


async def _build_agent(thread_id: str, user_id: str):
    """为一个特定 thread 构建 agent（含 sandbox）。

    仅在模块内部调用，外部通过 get_or_create_agent() 获取。
    """
    mcp_tools = await get_mcp_tools()
    skill_tools = get_skill_tools()
    search_tools = get_search_tools()
    file_tools = get_file_tools()

    opensandbox_backend = await get_or_create_sandbox(thread_id, user_id)

    def backend_factory(runtime):
        return CompositeBackend(
            default=opensandbox_backend,
            routes={
                "/memories/": StoreBackend(
                    runtime,
                    namespace=lambda ctx: ("memories",),
                ),
            },
        )

    agent_kwargs: dict = {}
    if USE_MONGO_PERSISTENCE:
        mongo_client = _get_mongo_client()
        agent_kwargs["checkpointer"] = MongoDBSaver(
            mongo_client,
            db_name=f"{MONGO_DB_NAME}_checkpoints",
        )
        store_db = mongo_client[f"{MONGO_DB_NAME}_store"]
        agent_kwargs["store"] = MongoDBStore(
            store_db["persistent_store"],
        )
        print(
            f"[MongoDB] 启用自定义持久化: "
            f"checkpointer={MONGO_DB_NAME}_checkpoints, "
            f"store={MONGO_DB_NAME}_store/persistent_store"
        )
    else:
        print("[持久化] 由 LangGraph Platform 自动管理")

    agent = create_deep_agent(
        model=DEFAULT_MODEL,
        tools=[utc_now, *file_tools, *search_tools, *mcp_tools, *skill_tools],
        backend=backend_factory,
        system_prompt=SYSTEM_PROMPT,
        memory=["/AGENTS.md", f"/memories/{user_id}/preferences.md"],
        subagents=get_sub_agents(),
        skills=["/skills"],
        name="deep_agent",
        **agent_kwargs,
    )
    return agent


async def get_or_create_agent(thread_id: str, user_id: str):
    """获取或创建指定 thread 的 agent 实例（带缓存 + Redis 持久化）。

    每个 thread 独占一个 agent + sandbox，避免并发冲突。
    使用 asyncio.Lock 防止并发时重复创建同一个 thread 的 agent。
    首次创建时自动将线程元数据写入 Redis。
    """
    if thread_id in _agent_cache:
        return _agent_cache[thread_id]

    async with _agent_lock:
        if thread_id in _agent_cache:
            return _agent_cache[thread_id]
        print(f"[Agent] 创建新 agent: thread_id={thread_id}, user_id={user_id}")

        # 若 Redis 无此线程记录则写入（API 侧可能已提前 create_thread）
        existing = await get_thread_meta(thread_id)
        if not existing:
            await save_thread_meta(thread_id, user_id)

        agent = await _build_agent(thread_id, user_id)
        _agent_cache[thread_id] = agent
        return agent


async def cleanup_thread(thread_id: str) -> bool:
    """清理指定 thread 的 agent、sandbox 和 Redis 元数据。

    Returns:
        True 表示清理成功，False 表示该 thread 不存在。
    """
    agent = _agent_cache.pop(thread_id, None)
    if agent is None and not await get_thread_meta(thread_id):
        return False

    await cleanup_sandbox(thread_id)
    await delete_thread_meta(thread_id)
    print(f"[Agent] 已清理: thread_id={thread_id}")
    return True


async def cleanup_all() -> int:
    """清理所有活跃的 agent 和 sandbox（用于服务器 shutdown）。

    Returns:
        清理的 thread 数量。
    """
    thread_ids = list(_agent_cache.keys())
    count = 0
    for tid in thread_ids:
        if await cleanup_thread(tid):
            count += 1
    return count


def list_active_threads() -> list[str]:
    """返回当前活跃（内存中已加载）的 thread ID 列表。"""
    return list(_agent_cache.keys())


def new_thread_id() -> str:
    """生成新的 thread ID。"""
    return str(uuid.uuid4())