"""共享的 sandbox 工具函数，供 tools 模块内部使用。

所有工具通过此模块获取已创建的 OpenSandbox sandbox 实例，
避免各自重复创建连接。
"""

from __future__ import annotations

import logging

from langchain_core.runnables import RunnableConfig

logger = logging.getLogger("milo.tools")

from deep_agent.opensandbox_backend import _backends


# ---------------------------------------------------------------------------
# Sandbox 获取
# ---------------------------------------------------------------------------

def get_sandbox_sync(config: RunnableConfig):
    """根据 RunnableConfig 中的 user_id 获取已存在的 OpenSandbox sandbox。

    sandbox 按 user 共享，在 graph._build_agent() 阶段通过
    get_or_create_sandbox() 创建并存入 _backends 缓存。

    Args:
        config: LangChain 运行时配置（自动注入），从中提取 user_id。

    Returns:
        SandboxSync 实例。

    Raises:
        RuntimeError: 如果对应用户的沙盒尚未初始化。
    """
    user_id = config["configurable"]["user_id"]
    backend = _backends.get(user_id)
    if backend is None:
        raise RuntimeError(
            f"沙盒尚未就绪 (user_id={user_id})，请确保 agent 已正确初始化"
        )
    return backend.sandbox
