"""Deep Agent graph for deployment."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from deepagents import create_deep_agent
from deepagents.middleware import SummarizationMiddleware
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from deep_agent.opensandbox_backend import get_or_create_sandbox
from deep_agent.sub_agents import get_sub_agents
from model_provider import deepseek_model
import os
from dotenv import load_dotenv

from tools.file_tool import get_file_tools
from tools.mcp_tool import get_mcp_tools
from tools.search_tool import get_search_tools
from tools.install_skill import get_skill_tools
from utils.path import get_root_path

root_path = get_root_path()

skill_path = os.path.join(root_path,'skills')

print(f"skill_path:${skill_path}\n")

load_dotenv()
# DEFAULT_MODEL = os.getenv("DEEP_AGENT_MODEL", "anthropic:claude-sonnet-4-6")
DEFAULT_MODEL=deepseek_model
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



root_path = get_root_path()
print(f"root_path:${root_path}\n")

async def build_agent(config:RunnableConfig):
    mcp_tools = await get_mcp_tools()
    skill_tools = get_skill_tools()
    search_tools = get_search_tools()
    file_tools = get_file_tools()
    thread_id = config["configurable"]["thread_id"]
    # 获取或创建 sandbox，同时将 thread_id ↔ sandbox 映射持久化到 Redis (localhost:6379)
    backend = await get_or_create_sandbox(thread_id)
    return create_deep_agent(
        model=DEFAULT_MODEL,
        tools=[utc_now,*file_tools,*search_tools,*mcp_tools,*skill_tools],
        backend=backend,
        system_prompt=SYSTEM_PROMPT,
        # backend=FilesystemBackend(
        #     root_dir=root_path,
        #     virtual_mode = True
        # ),
        memory=["/workspace/AGENTS.md", "/workspace/.deepagents/preferences.md"],
        subagents=get_sub_agents(),
        # middleware=[SummarizationMiddleware(
        #     model=DEFAULT_MODEL,
        #     backend=backend,
        #     trigger=("tokens", 100000),
        #     keep=("messages",5),
        # )],
        skills=["/skills"],
        # You can disable these if you want to run without interrupts
        # interrupt_on={
        #     "execute": True, "write_file": True},
        name="deep_agent",
    )



config = {
    "configurable":{
        "thread_id":"user123"
    }
}
agent = asyncio.run(build_agent(config))