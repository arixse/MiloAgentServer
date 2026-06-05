"""OpenSandbox backend for DeepAgents.

基于阿里巴巴 OpenSandbox 实现的 DeepAgents 异步沙盒后端。
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone

import asyncio
import redis.asyncio as aioredis

logger = logging.getLogger("milo.sandbox")
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
from pymongo import MongoClient

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

# MongoDB 持久化配置（复用 graph.py 的环境变量）
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "MiloAgent")
_mongo_client: MongoClient | None = None

# 需要在沙盒销毁前备份到 MongoDB 的关键文件列表
_PERSIST_FILES = [
    "/AGENTS.md",
    "/memories/",  # 目录递归备份
]

# 用于缓存不同 user_id 对应的沙盒后端实例（一个用户一个沙盒）
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


def _redis_key(user_id: str) -> str:
    """生成 Redis 键名（按 user_id 索引）。"""
    return f"{REDIS_KEY_PREFIX}:{user_id}"


async def _store_sandbox_mapping(user_id: str, sandbox_id: str) -> None:
    """将 user_id → sandbox 的映射关系存储到 Redis。"""
    r = await _get_redis()
    mapping = {
        "sandbox_id": sandbox_id,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "user_id": user_id,
    }
    await r.set(_redis_key(user_id), json.dumps(mapping))


async def _get_sandbox_mapping(user_id: str) -> dict | None:
    """从 Redis 查询 user_id 对应的 sandbox 映射。"""
    r = await _get_redis()
    data = await r.get(_redis_key(user_id))
    if data:
        return json.loads(data)
    return None


async def _delete_sandbox_mapping(user_id: str) -> None:
    """从 Redis 删除 user_id 对应的 sandbox 映射。"""
    r = await _get_redis()
    await r.delete(_redis_key(user_id))


class OpenSandboxBackend(BaseSandbox):
    """OpenSandbox 异步沙盒后端。

    实现了 DeepAgents 要求的文件读写与命令执行协议。
    通过后台线程定期调用 ``renew()`` 防止沙盒因超时而自动销毁。
    """

    def __init__(self, sandbox: SandboxSync, user_id: str = "", timeout_hours: float = SANDBOX_TIMEOUT_HOURS):
        self.sandbox = sandbox
        self._user_id = user_id
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
                    logger.debug("renew 成功: %s (timeout=%sh)", self.sandbox.id, self._timeout_hours)
                except Exception as e:
                    logger.warning("renew 失败: %s: %s", self.sandbox.id, e)

        self._renew_thread = threading.Thread(
            target=_renew_worker,
            name=f"sandbox-renew-{self.sandbox.id[:8]}",
            daemon=True,
        )
        self._renew_thread.start()
        logger.debug("续期线程已启动: %s (timeout=%sh)", self.sandbox.id, self._timeout_hours)

    def _stop_renew_loop(self) -> None:
        """停止后台续期线程。"""
        if self._renew_thread is None:
            return
        self._stop_renew.set()
        self._renew_thread.join(timeout=5)
        self._renew_thread = None
        logger.debug("续期线程已停止: %s", self.sandbox.id)

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
        """Close the sandbox: backup key files to MongoDB, stop renew loop, then kill."""
        # 1. 备份关键文件到 MongoDB（防止沙盒异常销毁导致记忆丢失）
        if self._user_id and self.sandbox:
            try:
                _backup_sandbox_files(self.sandbox, self._user_id)
            except Exception as e:
                logger.warning("沙盒备份失败: %s: %s", self.sandbox.id, e)
        # 2. 停止续期并销毁沙盒
        self._stop_renew_loop()
        if self.sandbox:
            self.sandbox.kill()

def _get_connection_config() -> ConnectionConfigSync:
    """获取 OpenSandbox 连接配置。"""
    return ConnectionConfigSync(
        domain=os.getenv("OPENSANDBOX_SERVER_URL", "http://182.254.183.29:8080"),
        use_server_proxy=True,
        api_key=os.getenv("OPENSANDBOX_API_KEY"),
    )


# 本地项目根目录下的 AGENTS.md 路径
_LOCAL_AGENTS_MD = os.path.join(os.path.dirname(__file__), "..", "..", "AGENTS.md")


# ---------------------------------------------------------------------------
# MongoDB 文件持久化 —— 沙盒销毁后保留 AGENTS.md 和 memories
# ---------------------------------------------------------------------------

def _get_mongo() -> MongoClient:
    """获取或创建 MongoDB 客户端（单例）。"""
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(MONGO_URI)
        logger.info("已连接到 MongoDB: %s", MONGO_URI)
    return _mongo_client


def _persist_file_to_mongo(user_id: str, file_path: str, content: bytes) -> None:
    """将单个文件内容持久化到 MongoDB。"""
    mongo = _get_mongo()
    db = mongo[MONGO_DB_NAME]
    collection = db["sandbox_files"]
    collection.update_one(
        {"user_id": user_id, "path": file_path},
        {
            "$set": {
                "content": content,
                "updated_at": datetime.now(tz=timezone.utc),
            }
        },
        upsert=True,
    )


def _restore_file_from_mongo(user_id: str, file_path: str) -> bytes | None:
    """从 MongoDB 恢复单个文件内容，不存在则返回 None。"""
    mongo = _get_mongo()
    db = mongo[MONGO_DB_NAME]
    collection = db["sandbox_files"]
    doc = collection.find_one({"user_id": user_id, "path": file_path})
    if doc and "content" in doc:
        return doc["content"]
    return None


def _backup_sandbox_files(sandbox: SandboxSync, user_id: str) -> int:
    """将沙盒中的关键文件备份到 MongoDB。

    备份文件列表见 _PERSIST_FILES。返回成功备份的文件数。
    """
    count = 0
    for file_path in _PERSIST_FILES:
        try:
            if file_path.endswith("/"):
                # 目录：用 tar 打包后读取
                result = sandbox.commands.run(
                    f"tar -czf /tmp/_persist.tar.gz -C {file_path} . 2>/dev/null"
                )
                if result.exit_code == 0:
                    content = sandbox.files.read_bytes("/tmp/_persist.tar.gz")
                    _persist_file_to_mongo(user_id, file_path, content)
                    count += 1
            else:
                content = sandbox.files.read_bytes(file_path)
                _persist_file_to_mongo(user_id, file_path, content)
                count += 1
        except Exception as e:
            logger.warning("文件备份失败: %s: %s", file_path, e)
    if count:
        logger.info("已备份 %s 个文件 (user_id=%s)", count, user_id)
    return count


def _restore_sandbox_files(sandbox: SandboxSync, user_id: str) -> int:
    """从 MongoDB 恢复关键文件到沙盒（覆盖沙盒中的默认文件）。

    仅恢复 MongoDB 中存在且非空的文件。返回成功恢复的文件数。
    """
    count = 0
    for file_path in _PERSIST_FILES:
        try:
            content = _restore_file_from_mongo(user_id, file_path)
            if not content:
                continue
            if file_path.endswith("/"):
                # 目录：解压 tar 包
                sandbox.files.write_file("/tmp/_persist.tar.gz", content)
                result = sandbox.commands.run(
                    f"mkdir -p {file_path}"
                    f" && tar -xzf /tmp/_persist.tar.gz -C {file_path}"
                    f" && rm -f /tmp/_persist.tar.gz"
                )
                if result.exit_code == 0:
                    count += 1
                    logger.info("已恢复目录: %s", file_path)
            else:
                sandbox.files.write_file(file_path, content)
                count += 1
                logger.info("已恢复文件: %s (%s bytes)", file_path, len(content))
        except Exception as e:
            logger.warning("文件恢复失败: %s: %s", file_path, e)
    if count:
        logger.info("已恢复 %s 个文件 (user_id=%s)", count, user_id)
    return count


# ---------------------------------------------------------------------------
# Skill zip 持久化 —— 避免重下载依赖外部 URL
# ---------------------------------------------------------------------------

def persist_skill_zip(user_id: str, skill_name: str, zip_content: bytes) -> None:
    """将 skill 的 zip 包持久化到 MongoDB。

    在沙盒意外销毁后，优先从 MongoDB 恢复，无需重新下载。

    Args:
        user_id: 用户 ID。
        skill_name: skill 名称。
        zip_content: skill zip 包的原始字节。
    """
    try:
        _persist_file_to_mongo(user_id, f"/skills/{skill_name}.zip", zip_content)
        logger.info("skill zip 已存储: %s (%s bytes)", skill_name, len(zip_content))
    except Exception as e:
        logger.warning("skill zip 存储失败: %s: %s", skill_name, e)


def restore_skill_zip(user_id: str, skill_name: str) -> bytes | None:
    """从 MongoDB 恢复 skill 的 zip 包。

    Args:
        user_id: 用户 ID。
        skill_name: skill 名称。

    Returns:
        zip 包字节，若未存储过则返回 None。
    """
    return _restore_file_from_mongo(user_id, f"/skills/{skill_name}.zip")


def list_persisted_skills(user_id: str) -> list[str]:
    """从 MongoDB 列出某用户已持久化的所有 skill 名称。

    Args:
        user_id: 用户 ID。

    Returns:
        skill 名称列表（无持久化记录时为空）。
    """
    try:
        mongo = _get_mongo()
        db = mongo[MONGO_DB_NAME]
        collection = db["sandbox_files"]
        prefix = "/skills/"
        cursor = collection.find(
            {"user_id": user_id, "path": {"$regex": "^/skills/.*\\.zip$"}},
            {"path": 1},
        )
        names = []
        for doc in cursor:
            path = doc.get("path", "")
            # 提取 skill 名称: /skills/{name}.zip → {name}
            name = path[len(prefix):-4] if path.endswith(".zip") else path[len(prefix):]
            if name:
                names.append(name)
        return names
    except Exception as e:
        logger.warning("列出 skill 失败 (user=%s): %s", user_id, e)
        return []


def _init_sandbox_filesystem(sandbox: SandboxSync, user_id: str) -> None:
    """初始化沙盒文件系统：创建必要目录，上传 AGENTS.md，并从 MongoDB 恢复持久化文件。

    仅在全新创建的沙盒上调用，重连的沙盒无需重复初始化。
    """
    # 1. 创建 /skills 和 /memories 目录
    sandbox.commands.run("mkdir -p /skills /memories")
    logger.info("已创建目录: /skills, /memories")

    # 1.5 确保 pip 可用（镜像可能未预装）
    pip_check = sandbox.commands.run(
        "python3 -m pip --version 2>/dev/null || "
        "python3 -m ensurepip --upgrade 2>/dev/null || "
        "apt-get update -qq 2>/dev/null && apt-get install -y -qq python3-pip 2>/dev/null; "
        "python3 -m pip --version 2>/dev/null && echo 'pip ready' || echo 'pip unavailable'"
    )
    if "pip ready" in (pip_check.logs.stdout[0].text if pip_check.logs.stdout else ""):
        logger.info("pip 已就绪")
    else:
        logger.warning("pip 未能安装，Python 包安装功能不可用")

    # 2. 上传本地 AGENTS.md 到沙盒根目录
    if os.path.isfile(_LOCAL_AGENTS_MD):
        with open(_LOCAL_AGENTS_MD, "rb") as f:
            content = f.read()
        sandbox.files.write_file("/AGENTS.md", content)
        logger.info("已上传 AGENTS.md → /AGENTS.md (%s bytes)", len(content))
    else:
        logger.info("本地 AGENTS.md 不存在 (%s)，跳过上传", _LOCAL_AGENTS_MD)

    # 3. 从 MongoDB 恢复之前持久化的文件（覆盖基线版本）
    _restore_sandbox_files(sandbox, user_id)


def _install_skill_from_url(sandbox: SandboxSync, skill_name: str, download_url: str) -> bytes:
    """从 URL 下载 skill zip 并安装到指定的 sandbox 中。

    Args:
        sandbox: 目标 SandboxSync 实例。
        skill_name: skill 名称。
        download_url: skill zip 包的下载地址。

    Returns:
        下载的 zip 包原始字节（供调用方缓存到 MongoDB）。

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
            zip_content = f.read()

        _install_skill_from_zip(sandbox, skill_name, zip_content)
        return zip_content
    finally:
        shutil.rmtree(local_tmpdir, ignore_errors=True)


def _install_skill_from_zip(sandbox: SandboxSync, skill_name: str, zip_content: bytes) -> None:
    """从 zip 字节直接安装 skill 到沙盒（无需下载）。

    Args:
        sandbox: 目标 SandboxSync 实例。
        skill_name: skill 名称。
        zip_content: skill zip 包的原始字节。

    Raises:
        RuntimeError: 解压失败。
    """
    remote_zip = f"/skills/{skill_name}.zip"
    sandbox.files.write_file(remote_zip, zip_content)

    result = sandbox.commands.run(
        f"mkdir -p /skills/{skill_name}"
        f" && unzip -o {remote_zip} -d /skills/{skill_name}"
        f" && rm -f {remote_zip}"
    )
    if result.exit_code != 0:
        stderr = result.logs.stderr[0].text if result.logs.stderr else ""
        raise RuntimeError(f"解压失败 (exit_code={result.exit_code}): {stderr}")


async def _restore_skills(user_id: str, sandbox: SandboxSync) -> None:
    """在 sandbox 意外销毁并重建后，从 MongoDB 恢复该用户之前安装的 skill。

    从 MongoDB sandbox_files 集合读取缓存的 zip 包直接解压，无需联网。
    单个 skill 恢复失败不会阻塞 sandbox 创建。

    Args:
        user_id: 用户 ID（skill 按 user 维度存储，跨会话保留）。
        sandbox: 新创建的 SandboxSync 实例。
    """
    skill_names = list_persisted_skills(user_id)
    if not skill_names:
        return

    logger.info("从 MongoDB 发现 %s 个 skill (user=%s)，开始恢复...", len(skill_names), user_id)
    restored = 0
    for skill_name in skill_names:
        try:
            zip_content = restore_skill_zip(user_id, skill_name)
            if not zip_content:
                logger.warning("skill 恢复跳过 (zip 为空): %s", skill_name)
                continue
            _install_skill_from_zip(sandbox, skill_name, zip_content)
            restored += 1
            logger.info("skill 恢复成功: %s", skill_name)
        except Exception as e:
            logger.warning("skill 恢复失败: %s: %s", skill_name, e)

    logger.info("skill 恢复完成: %s/%s", restored, len(skill_names))


def _create_sandbox_instance() -> SandboxSync:
    """创建新的 OpenSandbox 沙盒实例（长时间有效）。"""
    config = _get_connection_config()
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
    logger.info(
        "沙盒创建成功: %s timeout=%sh",
        sandbox.id, SANDBOX_TIMEOUT_HOURS
    )
    return sandbox


async def get_or_create_sandbox(user_id: str) -> OpenSandboxBackend:
    """获取当前用户的沙盒，如果不存在则创建一个新的。

    一个用户一个沙盒，所有线程共享。查找顺序：
    1. 内存缓存（当前进程）
    2. Redis 映射 → 尝试重连已有沙盒
    3. 以上均不可用 → 创建新沙盒并更新 Redis 映射

    Args:
        user_id: 用户 ID。
    """
    # 1. 优先从内存缓存查找
    if backend := _backends.get(user_id):
        return backend

    # 2. 查询 Redis 中的历史映射，尝试重连已有沙盒
    existing_mapping = await _get_sandbox_mapping(user_id)
    if existing_mapping:
        sandbox_id = existing_mapping["sandbox_id"]
        logger.info("发现已有 sandbox 映射: user=%s sandbox=%s", user_id, sandbox_id)
        try:
            # 尝试重连到已有的沙盒实例
            logger.info("正在重连 sandbox: %s", sandbox_id)
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
                logger.warning("sandbox 健康检查失败 (%s): %s", sandbox_id, health_err)
                sandbox.kill()
                raise

            backend = OpenSandboxBackend(sandbox, user_id=user_id)
            _backends[user_id] = backend
            logger.info("成功重连 sandbox: user=%s sandbox=%s", user_id, sandbox_id)
            return backend

        except Exception as e:
            logger.warning("sandbox 重连失败 (%s): %s，将创建新实例", sandbox_id, e)
            # 删除失效的 Redis 映射（创建新沙盒后会重新写入）
            await _delete_sandbox_mapping(user_id)

    # 3. 创建新的沙盒实例
    sandbox = _create_sandbox_instance()
    backend = OpenSandboxBackend(sandbox, user_id=user_id)

    # 初始化沙盒文件系统（目录 + AGENTS.md，仅新创建的沙盒）
    _init_sandbox_filesystem(sandbox, user_id)

    # 从 MongoDB 恢复该用户之前安装的 skill
    await _restore_skills(user_id, sandbox)

    _backends[user_id] = backend

    # 4. 将映射关系持久化到 Redis
    await _store_sandbox_mapping(user_id, backend.sandbox.id)
    logger.info("sandbox 映射已存储: user=%s sandbox=%s", user_id, backend.sandbox.id)

    return backend


def list_sandbox_users() -> list[str]:
    """返回当前活跃（内存中已加载）的 sandbox 用户 ID 列表。"""
    return list(_backends.keys())


async def cleanup_sandbox(user_id: str):
    """清理并销毁指定用户的沙盒实例。

    注意：skill 和 memories 已持久化到 MongoDB，此处不删除。
    """
    if backend := _backends.pop(user_id, None):
        backend.close()
    # 清理 Redis 中的 sandbox 映射记录
    await _delete_sandbox_mapping(user_id)
    logger.info("sandbox 映射已清理: user=%s", user_id)

