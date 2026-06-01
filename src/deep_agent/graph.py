"""Deep Agent graph for deployment."""

from __future__ import annotations

import asyncio
import contextlib
import os
from datetime import datetime, timezone

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from deepagents.middleware import SummarizationMiddleware
from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.store.mongodb import MongoDBStore
from pymongo import MongoClient

from deep_agent.opensandbox_backend import get_or_create_sandbox
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
print(f"skill_path:${skill_path}\n")
print(f"root_path:${root_path}\n")

# ---------------------------------------------------------------------------
# MongoDB / 持久化配置
# ---------------------------------------------------------------------------
# LangGraph Platform (langgraph dev / LangSmith Deployment) 会自动管理
# checkpointer 和 store，禁止传入自定义实例。
# 设置 USE_MONGO_PERSISTENCE=true 仅在独立运行（非 Platform）时启用 MongoDB。
USE_MONGO_PERSISTENCE = os.getenv("USE_MONGO_PERSISTENCE", "").lower() == "true"
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "MiloAgent")

# 共享 MongoDB 客户端（模块级别单例，仅 USE_MONGO_PERSISTENCE=true 时初始化）
_mongo_client: MongoClient | None = None


def _get_mongo_client() -> MongoClient:
    """获取共享的 MongoDB 客户端（延迟初始化）。"""
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(MONGO_URI)
        print(f"[MongoDB] 已连接到 {MONGO_URI}")
    return _mongo_client


# ---------------------------------------------------------------------------
# Model & system prompt
# ---------------------------------------------------------------------------
# DEFAULT_MODEL = os.getenv("DEEP_AGENT_MODEL", "anthropic:claude-sonnet-4-6")
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
# Agent builder
# ---------------------------------------------------------------------------
async def build_agent(config: RunnableConfig):
    mcp_tools = await get_mcp_tools()
    skill_tools = get_skill_tools()
    search_tools = get_search_tools()
    file_tools = get_file_tools()

    thread_id = config["configurable"]["thread_id"]
    user_id = config["configurable"]["user_id"]

    # 1. 获取或创建 sandbox（thread_id ↔ sandbox 映射已持久化到 Redis）
    opensandbox_backend = await get_or_create_sandbox(thread_id, user_id)

    # 2. CompositeBackend：默认走 sandbox（执行+文件），/memories/ 走 StoreBackend
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

    # 3. 持久化层：LangGraph Platform 自动管理，仅在独立运行时注入自定义 MongoDB
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
            "[MongoDB] 启用自定义持久化: "
            f"checkpointer={MONGO_DB_NAME}_checkpoints, "
            f"store={MONGO_DB_NAME}_store/persistent_store"
        )
    else:
        print("[持久化] 由 LangGraph Platform 自动管理")

    _agent = create_deep_agent(
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

    return _agent


config = {
    "configurable":{
        "thread_id":"fb768b1b-5059-4e34-8b00-d270c5fc9f5f",
        "user_id":"user_123"
    }
}

agent = asyncio.run(build_agent(config))