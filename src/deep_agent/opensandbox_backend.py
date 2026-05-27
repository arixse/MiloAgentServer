"""OpenSandbox backend for DeepAgents.

基于阿里巴巴 OpenSandbox 实现的 DeepAgents 异步沙盒后端。
"""

from __future__ import annotations

import os
from datetime import timedelta

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
    WriteResult,
)
from deepagents.backends.sandbox import BaseSandbox
from opensandbox import Sandbox

# 默认的沙盒镜像（OpenSandbox 官方提供的代码解释器镜像）
DEFAULT_SANDBOX_IMAGE = "opensandbox/code-interpreter:v1.0.1"

# 用于缓存不同 thread_id 对应的沙盒后端实例
_backends: dict[str, "OpenSandboxBackend"] = {}


class OpenSandboxBackend(BaseSandbox):
    """OpenSandbox 异步沙盒后端。

    实现了 DeepAgents 要求的异步文件读写与命令执行协议。
    """

    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox
        self._default_timeout = 300  # 默认执行超时时间（秒）

    @property
    def id(self) -> str:
        # OpenSandbox 的 sandbox 对象通常带有 id 属性作为唯一标识
        return getattr(self._sandbox, "id", "unknown-sandbox-id")

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        raise NotImplementedError("请使用 aexecute() 异步方法")

    async def aexecute(
            self, command: str, *, timeout: int | None = None
    ) -> ExecuteResponse:
        """在沙盒内异步执行 Shell 命令"""
        effective_timeout = timeout if timeout is not None else self._default_timeout
        # 调用 OpenSandbox 的命令执行接口
        execution = await self._sandbox.commands.run(
            command, timeout=timedelta(seconds=effective_timeout)
        )

        # 拼接标准输出和错误输出
        stdout = "".join([log.text for log in execution.logs.stdout]) if execution.logs.stdout else ""
        stderr = "".join([log.text for log in execution.logs.stderr]) if execution.logs.stderr else ""

        output = stdout
        if stderr:
            output += "\n" + stderr if output else stderr

        return ExecuteResponse(
            output=output,
            exit_code=execution.exit_code,
            truncated=False,
        )

    def write(self, file_path: str, content: str) -> WriteResult:
        raise NotImplementedError("请使用 awrite() 异步方法")

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

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        raise NotImplementedError("请使用 adownload_files() 异步方法")

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

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        raise NotImplementedError("请使用 aupload_files() 异步方法")

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


async def get_or_create_sandbox(thread_id: str) -> OpenSandboxBackend:
    """获取当前线程缓存的沙盒，如果不存在则创建一个新的。"""
    if backend := _backends.get(thread_id):
        return backend

    # 从环境变量获取 OpenSandbox Server 地址和镜像配置
    sandbox_server_url = os.environ.get("OPENSANDBOX_SERVER_URL", "http://localhost:8080")
    sandbox_image = os.environ.get("SANDBOX_IMAGE", DEFAULT_SANDBOX_IMAGE)

    # 创建 OpenSandbox 实例（设置 10 分钟超时）
    sandbox = await Sandbox.create(
        sandbox_image,
        timeout=timedelta(minutes=10),
        # 如果你的 OpenSandbox Server 不是默认地址，可以通过 client 参数传入
        # client=YourCustomClient(base_url=sandbox_server_url)
    )

    backend = OpenSandboxBackend(sandbox)
    _backends[thread_id] = backend
    return backend


async def cleanup_sandbox(thread_id: str):
    """在对话结束后清理并销毁指定的沙盒实例"""
    if backend := _backends.pop(thread_id, None):
        await backend.close()