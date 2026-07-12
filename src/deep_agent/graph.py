"""Deep Agent graph for deployment.

Agent 工厂模块 —— 按 thread_id 缓存 agent 实例，每个 thread 独占一个 sandbox。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

logger = logging.getLogger("milo.agent")
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

from deep_agent.opensandbox_backend import get_or_create_sandbox, cleanup_sandbox, list_sandbox_users
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
logger.debug("skill_path: %s", skill_path)
logger.debug("root_path: %s", root_path)

# ---------------------------------------------------------------------------
# MongoDB / 持久化配置
# ---------------------------------------------------------------------------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_USERNAME = os.getenv("MONGO_USERNAME", "")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD", "")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "MiloAgent")

_mongo_client: MongoClient | None = None
_checkpointer: MongoDBSaver | None = None


def _get_checkpointer() -> MongoDBSaver:
    """获取缓存的 MongoDBSaver 实例（用于无需 agent 的只读操作）。"""
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = MongoDBSaver(
            _get_mongo_client(),
            db_name=f"{MONGO_DB_NAME}_checkpoints",
        )
    return _checkpointer


def _get_mongo_client() -> MongoClient:
    global _mongo_client
    if _mongo_client is None:
        if MONGO_USERNAME and MONGO_PASSWORD:
            _mongo_client = MongoClient(
                MONGO_URI,
                username=MONGO_USERNAME,
                password=MONGO_PASSWORD,
            )
        else:
            _mongo_client = MongoClient(MONGO_URI)
        logger.info("已连接到 MongoDB: %s", MONGO_URI)
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
# Thread 持久化 —— MongoDB 存储线程元数据
# ---------------------------------------------------------------------------

def _thread_collection():
    """获取线程元数据的 MongoDB collection。"""
    client = _get_mongo_client()
    return client[MONGO_DB_NAME]["threads"]


async def save_thread_meta(
    thread_id: str,
    user_id: str = "default_user",
    metadata: dict | None = None,
) -> None:
    """持久化线程元数据到 MongoDB。"""
    if not user_id:
        raise ValueError("user_id cannot be empty")
    doc = {
        "thread_id": thread_id,
        "user_id": user_id,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "metadata": metadata,
    }
    _thread_collection().update_one(
        {"thread_id": thread_id},
        {"$set": doc},
        upsert=True,
    )


async def get_thread_meta(thread_id: str) -> dict | None:
    """从 MongoDB 读取线程元数据。"""
    doc = _thread_collection().find_one({"thread_id": thread_id})
    if doc:
        return {
            "thread_id": doc["thread_id"],
            "user_id": doc.get("user_id", ""),
            "created_at": doc.get("created_at", ""),
            "metadata": json.dumps(doc["metadata"]) if doc.get("metadata") else "",
        }
    return None


async def delete_thread_meta(thread_id: str) -> None:
    """从 MongoDB 删除线程元数据。"""
    _thread_collection().delete_one({"thread_id": thread_id})


async def list_all_threads() -> list[dict]:
    """从 MongoDB 列出所有线程元数据（管理用）。"""
    docs = _thread_collection().find().sort("created_at", -1)
    results = []
    for doc in docs:
        results.append({
            "thread_id": doc["thread_id"],
            "user_id": doc.get("user_id", ""),
            "created_at": doc.get("created_at", ""),
            "metadata": json.dumps(doc["metadata"]) if doc.get("metadata") else "",
        })
    return results


async def list_threads_by_user(user_id: str) -> list[dict]:
    """从 MongoDB 列出指定用户的所有线程元数据。"""
    docs = _thread_collection().find({"user_id": user_id}).sort("created_at", -1)
    results = []
    for doc in docs:
        results.append({
            "thread_id": doc["thread_id"],
            "user_id": doc.get("user_id", ""),
            "created_at": doc.get("created_at", ""),
            "metadata": json.dumps(doc["metadata"]) if doc.get("metadata") else "",
        })
    return results


# ---------------------------------------------------------------------------
# Agent 缓存 —— 每个 thread_id 独占一个 agent（及其 sandbox）
# ---------------------------------------------------------------------------
_agent_cache: dict[str, Any] = {}
_agent_lock = asyncio.Lock()


async def _build_agent(user_id: str):
    """为一个特定用户构建 agent（含共享 sandbox）。

    每个用户一个 sandbox，所有线程共享。仅在模块内部调用。
    """
    mcp_tools = await get_mcp_tools()
    skill_tools = get_skill_tools()
    search_tools = get_search_tools()
    file_tools = get_file_tools()

    opensandbox_backend = await get_or_create_sandbox(user_id)

    # MongoDB 持久化
    mongo_client = _get_mongo_client()
    store_db = mongo_client[f"{MONGO_DB_NAME}_store"]
    store = MongoDBStore(store_db["persistent_store"])

    agent_kwargs: dict = {}
    agent_kwargs["checkpointer"] = MongoDBSaver(
        mongo_client,
        db_name=f"{MONGO_DB_NAME}_checkpoints",
    )
    agent_kwargs["store"] = store
    logger.info(
        "MongoDB 持久化: checkpointer=%s_checkpoints, store=%s_store",
        MONGO_DB_NAME, MONGO_DB_NAME,
    )

    # 直接传 BackendProtocol 实例（不再使用 callable factory，避免 deprecation）
    backend = CompositeBackend(
        default=opensandbox_backend,
        routes={
            "/memories/": StoreBackend(
                store=store,
                namespace=lambda rt: ("memories",),
            ),
        },
    )

    agent = create_deep_agent(
        model=DEFAULT_MODEL,
        tools=[utc_now, *file_tools, *search_tools, *mcp_tools, *skill_tools],
        backend=backend,
        system_prompt=SYSTEM_PROMPT,
        memory=["/AGENTS.md", f"/memories/{user_id}/preferences.md"],
        subagents=get_sub_agents(),
        skills=["/skills"],
        name="deep_agent",
        **agent_kwargs,
    )
    return agent


async def get_or_create_agent(thread_id: str, user_id: str):
    """获取或创建指定 thread 的 agent 实例（带缓存 + MongoDB 持久化）。

    每个 thread 独占一个 agent + sandbox，避免并发冲突。
    使用 asyncio.Lock 防止并发时重复创建同一个 thread 的 agent。
    首次创建时自动将线程元数据写入 MongoDB。
    """
    if thread_id in _agent_cache:
        return _agent_cache[thread_id]

    async with _agent_lock:
        if thread_id in _agent_cache:
            return _agent_cache[thread_id]
        logger.info("创建新 agent: thread_id=%s, user_id=%s", thread_id, user_id)

        # 若 MongoDB 无此线程记录则写入（API 侧可能已提前 create_thread）
        existing = await get_thread_meta(thread_id)
        if not existing:
            await save_thread_meta(thread_id, user_id)

        agent = await _build_agent(user_id)
        _agent_cache[thread_id] = agent
        return agent


async def get_thread_state_direct(thread_id: str) -> dict:
    """直接从 MongoDB checkpoint 读取线程状态，不依赖 agent 或 sandbox。

    绕过了 get_or_create_agent → _build_agent → sandbox 创建流程，
    用于只读场景（如 /threads/{id}/state），避免等待 sandbox 就绪。

    Returns:
        checkpoint channel_values，无记录时返回空 dict。
    """
    config = {"configurable": {"thread_id": thread_id}}
    checkpointer = _get_checkpointer()
    tuple_ = await checkpointer.aget_tuple(config)
    if tuple_ and tuple_.checkpoint:
        return tuple_.checkpoint.get("channel_values", {}) or {}
    return {}


async def cleanup_thread(thread_id: str) -> bool:
    """清理指定 thread 的 agent 缓存和 MongoDB 元数据。

    注意：不销毁 sandbox，因为沙盒按用户共享，其他线程可能仍在使用。

    Returns:
        True 表示清理成功，False 表示该 thread 不存在。
    """
    agent = _agent_cache.pop(thread_id, None)
    meta = await get_thread_meta(thread_id)
    if agent is None and not meta:
        return False

    await delete_thread_meta(thread_id)
    logger.info("已清理线程: thread_id=%s", thread_id)
    return True


async def cleanup_all() -> int:
    """清理所有活跃的 agent 缓存和 sandbox（用于服务器 shutdown）。

    注意：不删除线程元数据或对话记录，用户重启后可继续对话。
    """
    # 1. 清空 agent 内存缓存（不删除持久化数据）
    thread_count = len(_agent_cache)
    _agent_cache.clear()

    # 2. 按 user 去重清理 sandbox
    sandbox_count = 0
    for user_id in list_sandbox_users():
        await cleanup_sandbox(user_id)
        sandbox_count += 1

    logger.info("已清理 %s 个 agent 缓存, %s 个 sandbox（线程和对话记录已保留）",
                thread_count, sandbox_count)
    return thread_count


def list_active_threads() -> list[str]:
    """返回当前活跃（内存中已加载）的 thread ID 列表。"""
    return list(_agent_cache.keys())


def new_thread_id() -> str:
    """生成新的 thread ID。"""
    return str(uuid.uuid4())