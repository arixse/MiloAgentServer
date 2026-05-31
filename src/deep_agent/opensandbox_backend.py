"""OpenSandbox backend for DeepAgents.

基于阿里巴巴 OpenSandbox 实现的 DeepAgents 异步沙盒后端。
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import asyncio
import redis.asyncio as aioredis
from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
    WriteResult,
)
from deepagents.backends.sandbox import BaseSandbox
from opensandbox import Sandbox
from dotenv import load_dotenv
from opensandbox.config import ConnectionConfig

load_dotenv()

# 默认的沙盒镜像（OpenSandbox 官方提供的代码解释器镜像）
DEFAULT_SANDBOX_IMAGE = "opensandbox/code-interpreter:v1.0.1"

# Redis 连接配置
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_KEY_PREFIX = "deep_agent:sandbox"

# 全局 Redis 客户端（延迟初始化）
_redis_client: aioredis.Redis | None = None

# 用于缓存不同 thread_id 对应的沙盒后端实例
_backends: dict[str, "OpenSandboxBackend"] = {}


async def _get_redis() -> aioredis.Redis:
    """获取或创建 Redis 异步客户端（单例模式）。"""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True,
        )
    return _redis_client


def _redis_key(thread_id: str) -> str:
    """生成 Redis 键名。"""
    return f"{REDIS_KEY_PREFIX}:{thread_id}"


async def _store_sandbox_mapping(thread_id: str, sandbox_id: str) -> None:
    """将 thread_id → sandbox 的映射关系存储到 Redis。"""
    r = await _get_redis()
    mapping = {
        "sandbox_id": sandbox_id,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "thread_id": thread_id,
    }
    await r.set(_redis_key(thread_id), json.dumps(mapping))


async def _get_sandbox_mapping(thread_id: str) -> dict | None:
    """从 Redis 查询 thread_id 对应的 sandbox 映射。"""
    r = await _get_redis()
    data = await r.get(_redis_key(thread_id))
    if data:
        return json.loads(data)
    return None


async def _delete_sandbox_mapping(thread_id: str) -> None:
    """从 Redis 删除 thread_id 对应的 sandbox 映射。"""
    r = await _get_redis()
    await r.delete(_redis_key(thread_id))


class OpenSandboxBackend(BaseSandbox):
    """OpenSandbox 异步沙盒后端。

    实现了 DeepAgents 要求的文件读写与命令执行协议。
    所有同步方法内部委托给对应的异步方法，确保在任何调用路径下都能正常工作。
    """

    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox
        self._default_timeout = 300  # 默认执行超时时间（秒）

    @property
    def id(self) -> str:
        # OpenSandbox 的 sandbox 对象通常带有 id 属性作为唯一标识
        return getattr(self._sandbox, "id", "unknown-sandbox-id")

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        return asyncio.run(self.aexecute(command, timeout=timeout))

    async def aexecute(
            self, command: str, *, timeout: int | None = None
    ) -> ExecuteResponse:
        """在沙盒内异步执行 Shell 命令"""
        effective_timeout = timeout if timeout is not None else self._default_timeout
        # 调用 OpenSandbox 的命令执行接口
        print(f"执行命令: {command}")
        execution = await self._sandbox.commands.run(
            command
        )

        # 拼接标准输出和错误输出
        stdout = "\n".join([log.text for log in execution.logs.stdout]) if execution.logs.stdout else ""
        stderr = "\n".join([log.text for log in execution.logs.stderr]) if execution.logs.stderr else ""

        output = stdout
        if stderr:
            output += "\n" + stderr if output else stderr

        return ExecuteResponse(
            output=output,
            exit_code=execution.exit_code,
            truncated=False,
        )

    # ------------------------------------------------------------------
    # write / awrite
    # ------------------------------------------------------------------

    def write(self, file_path: str, content: str) -> WriteResult:
        return asyncio.run(self.awrite(file_path, content))

    async def awrite(self, file_path: str, content: str) -> WriteResult:
        """异步写入文件到沙盒内"""
        try:
            # OpenSandbox 写入文件需要传入 WriteEntry 列表
            from opensandbox.models import WriteEntry
            await self._sandbox.files.write_files([
                WriteEntry(path=file_path, data=content, mode=0o644)
            ])
            return WriteResult(path=file_path, files_update=None)
        except Exception as e:
            return WriteResult(error=f"写入文件 '{file_path}' 失败: {e}")

    # ------------------------------------------------------------------
    # download_files / adownload_files
    # ------------------------------------------------------------------

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        return asyncio.run(self.adownload_files(paths))

    async def adownload_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """异步从沙盒内下载（读取）文件"""
        responses: list[FileDownloadResponse] = []
        for path in paths:
            try:
                # 读取文件内容（返回 bytes 或 str，根据 SDK 版本适配）
                content = await self._sandbox.files.read_file(path)
                # 确保 content 为 bytes 格式以适配协议
                if isinstance(content, str):
                    content = content.encode("utf-8")
                responses.append(
                    FileDownloadResponse(path=path, content=content, error=None)
                )
            except Exception as e:
                responses.append(
                    FileDownloadResponse(path=path, content=b"", error=str(e))
                )
        return responses

    # ------------------------------------------------------------------
    # upload_files / aupload_files
    # ------------------------------------------------------------------

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        return asyncio.run(self.aupload_files(files))

    async def aupload_files(
            self, files: list[tuple[str, bytes]]
    ) -> list[FileUploadResponse]:
        """异步上传文件到沙盒内"""
        responses: list[FileUploadResponse] = []
        from opensandbox.models import WriteEntry

        # 准备批量写入的条目
        write_entries = []
        for path, content in files:
            write_entries.append(WriteEntry(path=path, data=content, mode=0o644))

        try:
            await self._sandbox.files.write_files(write_entries)
            for path, _ in files:
                responses.append(FileUploadResponse(path=path, error=None))
        except Exception as e:
            for path, _ in files:
                responses.append(FileUploadResponse(path=path, error=str(e)))
        return responses

    async def close(self):
        """销毁沙盒实例，释放资源"""
        await self._sandbox.kill()


def _get_connection_config() -> ConnectionConfig:
    """获取 OpenSandbox 连接配置。"""
    return ConnectionConfig(
        domain="http://182.254.183.29:8080",
        use_server_proxy=True,
        api_key=os.getenv("OPENSANDBOX_API_KEY"),
    )


async def _create_sandbox_instance() -> Sandbox:
    """创建新的 OpenSandbox 沙盒实例。"""
    config = _get_connection_config()
    print("------------------restart----------------------")
    sandbox = await Sandbox.create(
        "opensandbox/code-interpreter:v1.0.2",
        connection_config=config,
        entrypoint=["/opt/opensandbox/code-interpreter.sh"],
        env={
            "PYTHON_VERSION": "3.11",
            "JAVA_VERSION": "17",
            "NODE_VERSION": "20",
            "GO_VERSION": "1.24",
        },
    )
    return sandbox


async def get_or_create_sandbox(thread_id: str) -> OpenSandboxBackend:
    """获取当前线程缓存的沙盒，如果不存在则创建一个新的。

    查找顺序：
    1. 内存缓存（当前会话）
    2. Redis 映射 → 尝试重连已有沙盒
    3. 以上均不可用 → 创建新沙盒并更新 Redis 映射
    """
    # 1. 优先从内存缓存查找
    if backend := _backends.get(thread_id):
        return backend

    # 2. 查询 Redis 中的历史映射，尝试重连已有沙盒
    existing_mapping = await _get_sandbox_mapping(thread_id)
    if existing_mapping:
        sandbox_id = existing_mapping["sandbox_id"]
        print(
            f"[Redis] 发现已存在的 sandbox 映射: thread_id={thread_id}, "
            f"sandbox_id={sandbox_id}, "
            f"created_at={existing_mapping['created_at']}"
        )
        try:
            # 尝试重连到已有的沙盒实例
            print(f"[Redis] 正在尝试重连 sandbox: {sandbox_id} ...")
            config = _get_connection_config()
            sandbox = await Sandbox.connect(
                sandbox_id,
                connection_config=config,
                connect_timeout=timedelta(seconds=10),
            )
            # 健康检查：执行一个简单命令验证沙盒是否真正可用
            try:
                result = await sandbox.commands.run(
                    "echo ok"
                )
                if result.exit_code != 0:
                    raise RuntimeError(
                        f"健康检查失败，exit_code={result.exit_code}"
                    )
            except Exception as health_err:
                print(
                    f"[Redis] sandbox 健康检查失败 (sandbox_id={sandbox_id}): {health_err}"
                )
                await sandbox.kill()
                raise

            backend = OpenSandboxBackend(sandbox)
            _backends[thread_id] = backend
            print(
                f"[Redis] ✓ 成功重连 sandbox: thread_id={thread_id}, "
                f"sandbox_id={sandbox_id}"
            )
            return backend

        except Exception as e:
            print(
                f"[Redis] ✗ sandbox 重连失败 (sandbox_id={sandbox_id}): {e}，"
                f"将创建新实例并更新 Redis 映射"
            )
            # 删除失效的 Redis 映射（创建新沙盒后会重新写入）
            await _delete_sandbox_mapping(thread_id)

    # 3. 创建新的沙盒实例
    sandbox = await _create_sandbox_instance()
    backend = OpenSandboxBackend(sandbox)
    _backends[thread_id] = backend

    # 4. 将映射关系持久化到 Redis
    await _store_sandbox_mapping(thread_id, backend.id)
    print(
        f"[Redis] sandbox 映射已存储: thread_id={thread_id}, "
        f"sandbox_id={backend.id}"
    )

    return backend


async def cleanup_sandbox(thread_id: str):
    """在对话结束后清理并销毁指定的沙盒实例"""
    if backend := _backends.pop(thread_id, None):
        await backend.close()
    # 同时清理 Redis 中的映射记录
    await _delete_sandbox_mapping(thread_id)
    print(f"[Redis] sandbox 映射已清理: thread_id={thread_id}")

