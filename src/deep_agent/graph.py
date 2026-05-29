"""Deep Agent graph for deployment."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from daytona import Daytona, DaytonaConfig, CreateSandboxFromSnapshotParams
from deepagents import create_deep_agent
from deepagents.middleware import SummarizationMiddleware
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from deep_agent.sub_agents import get_sub_agents
from model_provider import deepseek_model
from langchain_daytona import DaytonaSandbox
from langgraph.checkpoint.memory import MemorySaver
import os
from dotenv import load_dotenv

from tools.file_tool import read_file, save_to_pdf, save_to_markdown, generate_download_url
from tools.mcp_tool import get_mcp_tools
from tools.search_tool import search_tool, fetch_content
from tools.install_skill import install_skill_from_url
from utils.path import get_root_path

root_path = get_root_path()

skill_path = os.path.join(root_path,'skills')

print(f"skill_path:${skill_path}\n")

load_dotenv()
# DEFAULT_MODEL = os.getenv("DEEP_AGENT_MODEL", "anthropic:claude-sonnet-4-6")
DEFAULT_MODEL=deepseek_model
checkpointer = MemorySaver()
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
daytona_config = DaytonaConfig(
    api_key=os.getenv("DAYTONA_API_KEY")
)

mcp_tools = asyncio.run(get_mcp_tools())

@tool
def utc_now() -> str:
    """Return the current UTC timestamp in ISO format."""
    return datetime.now(tz=timezone.utc).isoformat()



root_path = get_root_path()
print(f"root_path:${root_path}\n")
client = Daytona(config=daytona_config)

def build_agent(config:RunnableConfig):
    thread_id = config["configurable"]["thread_id"]
    try:
        sandbox = client.get(f"sandbox_{thread_id}")
        print(f"find one:{thread_id}")
        print(sandbox)
    except Exception:
        print(f"not find one:{thread_id}")
        try:
            sandbox = client.create(
                CreateSandboxFromSnapshotParams(
                    name=f"sandbox_{thread_id}",
                    auto_delete_interval=3600,  # TTL: clean up when idle
                )
            )
        except Exception as e:
            raise ValueError(f"Failed to create sandbox: {e}")
    backend = DaytonaSandbox(sandbox=sandbox)
    return create_deep_agent(
        model=DEFAULT_MODEL,
        tools=[utc_now, install_skill_from_url,search_tool,read_file,save_to_pdf,save_to_markdown,generate_download_url,fetch_content,*mcp_tools],
        backend=backend,
        system_prompt=SYSTEM_PROMPT,
        # backend=FilesystemBackend(
        #     root_dir=root_path,
        #     virtual_mode = True
        # ),
        memory=["/home/daytona/AGENTS.md", "/home/daytona/.deepagents/preferences.md"],
        subagents=get_sub_agents(),
        # middleware=[SummarizationMiddleware(
        #     model=DEFAULT_MODEL,
        #     backend=backend,
        #     trigger=("tokens", 100000),
        #     keep=("messages",5),
        # )],
        checkpointer=checkpointer,
        skills=["/skills"],
        # You can disable these if you want to run without interrupts
        # interrupt_on={
        #     "execute": True, "write_file": True},
        name="deep_agent",
    )



