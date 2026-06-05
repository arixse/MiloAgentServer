"""OpenSandbox backend for DeepAgents.

基于阿里巴巴 OpenSandbox 实现的 DeepAgents 异步沙盒后端。
"""

from __future__ import annotations

import json
import os
import threading
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
from opensandbox import Sandbox, SandboxSync
from dotenv import load_dotenv
from opensandbox.config import ConnectionConfig, ConnectionConfigSync
from opensandbox.models.execd import RunCommandOpts

load_dotenv()

# 默认的沙盒镜像（OpenSandbox 官方提供的代码解释器镜像）
DEFAULT_SANDBOX_IMAGE = "opensandbox/code-interpreter:v1.0.1"

# ---------------------------------------------------------------------------
# 沙盒生命周期配置
# ---------------------------------------------------------------------------
# 沙盒总存活时间（可通过 SANDBOX_TIMEOUT_HOURS 环境变量覆盖）
SANDBOX_TIMEOUT_HOURS = float(os.getenv("SANDBOX_TIMEOUT_HOURS", "24"))
# 续期间隔 = 存活时间的 80%，确保在过期前提前续期
SANDBOX_RENEW_HOURS = SANDBOX_TIMEOUT_HOURS * 0.8

# Redis 连接配置
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_KEY_PREFIX = "milo_agent:sandbox"

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
    通过后台线程定期调用 ``renew()`` 防止沙盒因超时而自动销毁。
    """

    def __init__(self, sandbox: SandboxSync, timeout_hours: float = SANDBOX_TIMEOUT_HOURS):
        self.sandbox = sandbox
        self._timeout_hours = timeout_hours
        self._renew_interval = timeout_hours * 0.8
        self._stop_renew = threading.Event()
        self._renew_thread: threading.Thread | None = None
        self._start_renew_loop()

    # ------------------------------------------------------------------
    # 后台续期
    # ------------------------------------------------------------------

    def _start_renew_loop(self) -> None:
        """启动后台守护线程，定期调用 renew() 续期沙盒。"""
        interval_seconds = self._renew_interval * 3600

        def _renew_worker() -> None:
            renew_timeout = timedelta(hours=self._timeout_hours)
            while not self._stop_renew.is_set():
                # 等待续期间隔，但可被 stop 事件提前唤醒
                if self._stop_renew.wait(timeout=interval_seconds):
                    return
                try:
                    self.sandbox.renew(renew_timeout)
                    print(
                        f"[Sandbox {self.sandbox.id}] renew 成功 "
                        f"(timeout={self._timeout_hours}h)"
                    )
                except Exception as e:
                    print(
                        f"[Sandbox {self.sandbox.id}] renew 失败: {e}"
                    )

        self._renew_thread = threading.Thread(
            target=_renew_worker,
            name=f"sandbox-renew-{self.sandbox.id[:8]}",
            daemon=True,
        )
        self._renew_thread.start()
        print(
            f"[Sandbox {self.sandbox.id}] 已启动续期线程 "
            f"(timeout={self._timeout_hours}h, interval={self._renew_interval}h)"
        )

    def _stop_renew_loop(self) -> None:
        """停止后台续期线程。"""
        if self._renew_thread is None:
            return
        self._stop_renew.set()
        self._renew_thread.join(timeout=5)
        self._renew_thread = None
        print(f"[Sandbox {self.sandbox.id}] 续期线程已停止")

    # ------------------------------------------------------------------
    # Protocol methods
    # ------------------------------------------------------------------

    def id(self) -> str:
        return self.sandbox.id

    def execute(
            self,
            command: str,
            *,
            timeout: int | None = None,
    ) -> ExecuteResponse:
        """Execute a shell command inside the sandbox."""
        result = self.sandbox.commands.run(
            command,
            opts=RunCommandOpts(
                timeout=timedelta(seconds=timeout) if timeout else None,
            )
        )
        output = result.logs.stdout[0].text if result.logs.stdout else ''
        if result.logs.stderr:
            output += f"\n<stderr>{result.logs.stderr[0].text}</stderr>"
        return ExecuteResponse(
            exit_code=result.exit_code,
            output=output,
        )

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """Download files from the sandbox."""
        responses = []
        for path in paths:
            content = self.sandbox.files.read_bytes(path)
            responses.append(FileDownloadResponse(path=path, content=content, error=None))
        return responses

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """Upload files into the sandbox."""
        responses = []
        for path, content in files:
            if not path.startswith("/"):
                responses.append(FileUploadResponse(path=path, error="invalid_path"))
                continue
            self.sandbox.files.write_file(path, content)
            responses.append(FileUploadResponse(path=path, error=None))
        return responses

    def close(self) -> None:
        """Close the sandbox: stop renew loop, then kill."""
        self._stop_renew_loop()
        if self.sandbox:
            self.sandbox.kill()

def _get_connection_config() -> ConnectionConfigSync:
    """获取 OpenSandbox 连接配置。"""
    domain = os.getenv("OPENSANDBOX_SERVER_URL", "http://182.254.183.29:8080").rstrip("/")
    return ConnectionConfigSync(
        domain=domain,
        use_server_proxy=True,
        api_key=os.getenv("OPENSANDBOX_API_KEY"),
    )


# 本地项目根目录下的 AGENTS.md 路径
_LOCAL_AGENTS_MD = os.path.join(os.path.dirname(__file__), "..", "..", "AGENTS.md")


def _init_sandbox_filesystem(sandbox: SandboxSync) -> None:
    """初始化沙盒文件系统：创建必要目录并上传 AGENTS.md。

    仅在全新创建的沙盒上调用，重连的沙盒无需重复初始化。
    """
    # 1. 创建 /skills 和 /memories 目录
    sandbox.commands.run("mkdir -p /skills /memories")
    print("[Sandbox Init] 已创建目录: /skills, /memories")

    # 1.5 确保 pip 可用（镜像可能未预装）
    pip_check = sandbox.commands.run(
        "python3 -m pip --version 2>/dev/null || "
        "python3 -m ensurepip --upgrade 2>/dev/null || "
        "apt-get update -qq 2>/dev/null && apt-get install -y -qq python3-pip 2>/dev/null; "
        "python3 -m pip --version 2>/dev/null && echo 'pip ready' || echo 'pip unavailable'"
    )
    if "pip ready" in (pip_check.logs.stdout[0].text if pip_check.logs.stdout else ""):
        print("[Sandbox Init] pip 已就绪")
    else:
        print("[Sandbox Init] WARNING: pip 未能安装，Python 包安装功能不可用")

    # 2. 上传本地 AGENTS.md 到沙盒根目录
    if os.path.isfile(_LOCAL_AGENTS_MD):
        with open(_LOCAL_AGENTS_MD, "rb") as f:
            content = f.read()
        sandbox.files.write_file("/AGENTS.md", content)
        print(f"[Sandbox Init] 已上传 AGENTS.md → /AGENTS.md "
              f"({len(content)} bytes)")
    else:
        print(f"[Sandbox Init] 本地 AGENTS.md 不存在 ({_LOCAL_AGENTS_MD})，跳过上传")


def _install_skill_from_url(sandbox: SandboxSync, skill_name: str, download_url: str) -> None:
    """从 URL 下载 skill zip 并安装到指定的 sandbox 中。

    供 skill 恢复流程使用，与 install_skill.py 中的下载安装逻辑一致。

    Args:
        sandbox: 目标 SandboxSync 实例。
        skill_name: skill 名称。
        download_url: skill zip 包的下载地址。

    Raises:
        RuntimeError: 下载或解压失败。
    """
    import shutil
    import tempfile

    import httpx

    filename = download_url.rstrip("/").rsplit("/", 1)[-1] or f"{skill_name}.zip"
    local_tmpdir = tempfile.mkdtemp(prefix="skill_restore_")
    try:
        local_zip = os.path.join(local_tmpdir, filename)
        with httpx.Client(follow_redirects=True, timeout=120) as http:
            with http.stream("GET", download_url) as resp:
                resp.raise_for_status()
                with open(local_zip, "wb") as f:
                    for chunk in resp.iter_bytes(64 * 1024):
                        f.write(chunk)

        with open(local_zip, "rb") as f:
            sandbox.files.write_file(f"/skills/{filename}", f.read())

        result = sandbox.commands.run(
            f"mkdir -p /skills/{skill_name}"
            f" && unzip -o /skills/{filename} -d /skills/{skill_name}"
            f" && rm -f /skills/{filename}"
        )
        if result.exit_code != 0:
            stderr = result.logs.stderr[0].text if result.logs.stderr else ""
            raise RuntimeError(f"解压失败 (exit_code={result.exit_code}): {stderr}")
    finally:
        shutil.rmtree(local_tmpdir, ignore_errors=True)


async def _restore_skills(user_id: str, sandbox: SandboxSync) -> None:
    """在 sandbox 意外销毁并重建后，从 Redis 记录中恢复该用户之前安装的 skill。

    单个 skill 恢复失败不会阻塞 sandbox 创建，会打印错误日志后继续处理其余 skill。

    Args:
        user_id: 用户 ID（skill 按 user 维度存储，跨会话保留）。
        sandbox: 新创建的 SandboxSync 实例。
    """
    # lazy import 避免与 sandbox_utils 之间的循环依赖
    from tools.sandbox_utils import get_installed_skills

    skills = get_installed_skills(user_id)
    if not skills:
        return

    print(f"[Skill Restore] 发现用户 {user_id} 的 {len(skills)} 个已安装 skill，开始恢复...")
    restored = 0
    for skill_name, download_url in skills.items():
        try:
            _install_skill_from_url(sandbox, skill_name, download_url)
            restored += 1
            print(f"[Skill Restore] ✓ {skill_name}")
        except Exception as e:
            print(f"[Skill Restore] ✗ {skill_name}: {e}")

    print(f"[Skill Restore] 恢复完成: {restored}/{len(skills)}")


def _create_sandbox_instance() -> SandboxSync:
    """创建新的 OpenSandbox 沙盒实例（长时间有效）。

    包含重试机制：OpenSandbox 服务器可能偶尔返回临时性错误（如镜像未缓存），
    最多重试 3 次，指数退避。
    """
    config = _get_connection_config()

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            sandbox = SandboxSync.create(
                "opensandbox/code-interpreter:v1.0.2",
                connection_config=config,
                timeout=timedelta(hours=SANDBOX_TIMEOUT_HOURS),
                entrypoint=["/opt/opensandbox/code-interpreter.sh"],
                env={
                    "PYTHON_VERSION": "3.11",
                    "JAVA_VERSION": "17",
                    "NODE_VERSION": "20",
                    "GO_VERSION": "1.24",
                },
            )
            print(
                f"[Sandbox] 创建成功: id={sandbox.id}, "
                f"timeout={SANDBOX_TIMEOUT_HOURS}h"
                + (f" (第 {attempt + 1} 次尝试)" if attempt > 0 else "")
            )
            return sandbox
        except Exception as e:
            last_error = e
            if attempt < 2:
                wait = 2 ** attempt  # 1s, 2s
                print(f"[Sandbox] 创建失败 (第 {attempt + 1} 次尝试): {e}，{wait}s 后重试...")
                import time
                time.sleep(wait)

    raise RuntimeError(
        f"沙盒创建失败（已重试 3 次）: {last_error}"
    ) from last_error


async def get_or_create_sandbox(thread_id: str, user_id: str) -> OpenSandboxBackend:
    """获取当前线程缓存的沙盒，如果不存在则创建一个新的。

    查找顺序：
    1. 内存缓存（当前会话）
    2. Redis 映射 → 尝试重连已有沙盒
    3. 以上均不可用 → 创建新沙盒并更新 Redis 映射

    Args:
        thread_id: 对话线程 ID（sandbox 按 thread 隔离）。
        user_id: 用户 ID（用于 skill 恢复，按 user 维度）。
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
            sandbox = SandboxSync.connect(
                sandbox_id,
                connection_config=config,
                connect_timeout=timedelta(seconds=10),
            )
            # 健康检查：执行一个简单命令验证沙盒是否真正可用
            try:
                result = sandbox.commands.run(
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
                sandbox.kill()
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
    sandbox = _create_sandbox_instance()
    backend = OpenSandboxBackend(sandbox)

    # 初始化沙盒文件系统（目录 + AGENTS.md，仅新创建的沙盒）
    _init_sandbox_filesystem(sandbox)

    # 从 Redis 记录中恢复该用户之前安装的 skill（sandbox 意外销毁后的自动恢复）
    await _restore_skills(user_id, sandbox)

    _backends[thread_id] = backend

    # 4. 将映射关系持久化到 Redis
    await _store_sandbox_mapping(thread_id, backend.sandbox.id)
    print(
        f"[Redis] sandbox 映射已存储: thread_id={thread_id}, "
        f"sandbox_id={backend.sandbox.id}"
    )

    return backend


async def cleanup_sandbox(thread_id: str):
    """在对话结束后清理并销毁指定的沙盒实例。

    注意：skill 记录属于用户而非会话，此处不删除。
    """
    if backend := _backends.pop(thread_id, None):
        backend.close()
    # 清理 Redis 中的 sandbox 映射记录
    await _delete_sandbox_mapping(thread_id)
    print(f"[Redis] sandbox 映射已清理: thread_id={thread_id}")

