"""共享的 sandbox 工具函数，供 tools 模块内部使用。

所有工具通过此模块获取已创建的 OpenSandbox sandbox 实例，
避免各自重复创建连接。同时负责 skill 安装记录的持久化追踪，
确保 sandbox 意外销毁后能自动恢复已安装的 skill。
"""

from __future__ import annotations

import os

import redis
from langchain_core.runnables import RunnableConfig

from deep_agent.opensandbox_backend import _backends

# ---------------------------------------------------------------------------
# Redis 连接配置（与 opensandbox_backend.py 保持一致）
# ---------------------------------------------------------------------------
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_KEY_PREFIX = "milo_agent:sandbox"

_sync_redis: redis.Redis | None = None


def _get_sync_redis() -> redis.Redis:
    """获取同步 Redis 客户端（单例，供 sync 工具函数使用）。"""
    global _sync_redis
    if _sync_redis is None:
        _sync_redis = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True,
        )
    return _sync_redis


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


# ---------------------------------------------------------------------------
# Skill 安装追踪（Redis 持久化，按 user 维度存储）
#
# skill 和长期记忆属于用户，不属于单个会话。即使用户关闭所有会话，
# 已安装的 skill 记录仍然保留，下次任意会话重建 sandbox 时自动恢复。
# ---------------------------------------------------------------------------

def _skill_key(user_id: str) -> str:
    """生成 user 维度的 skill 记录 Redis key。"""
    return f"{REDIS_KEY_PREFIX}:user:{user_id}:skills"


def record_skill_install(user_id: str, skill_name: str, download_url: str) -> None:
    """记录一次成功的 skill 安装到 Redis（按 user 维度存储）。

    以 hash 结构存储：``{prefix}:user:{user_id}:skills`` → ``{skill_name: download_url}``。
    当任意会话的 sandbox 意外销毁后重建时，会根据这些记录自动重新下载安装。

    Args:
        user_id: 用户 ID。
        skill_name: skill 名称（从 SKILL.md frontmatter 解析）。
        download_url: skill zip 包的下载地址。
    """
    try:
        r = _get_sync_redis()
        r.hset(_skill_key(user_id), skill_name, download_url)
        print(f"[Skill Tracking] ✓ 已记录: {skill_name} (user={user_id})")
    except Exception as e:
        print(f"[Skill Tracking] ✗ 记录失败 ({skill_name}): {e}")


def get_installed_skills(user_id: str) -> dict[str, str]:
    """获取某个用户下所有已安装 skill 的记录。

    Args:
        user_id: 用户 ID。

    Returns:
        dict: ``{skill_name: download_url}``，无记录时返回空 dict。
    """
    try:
        r = _get_sync_redis()
        return r.hgetall(_skill_key(user_id)) or {}
    except Exception as e:
        print(f"[Skill Tracking] 读取记录失败 (user={user_id}): {e}")
        return {}


def delete_skill_records(user_id: str) -> None:
    """删除某个用户下所有 skill 安装记录。

    注意：正常情况下不应调用此函数，因为 skill 属于用户而非会话。
    仅用于管理操作（如用户注销、数据清理）。

    Args:
        user_id: 用户 ID。
    """
    try:
        r = _get_sync_redis()
        r.delete(_skill_key(user_id))
        print(f"[Skill Tracking] 已清理记录 (user={user_id})")
    except Exception as e:
        print(f"[Skill Tracking] 清理记录失败 (user={user_id}): {e}")
