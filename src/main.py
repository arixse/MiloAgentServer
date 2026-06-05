"""MiloAgent — FastAPI 入口。

启动:  uvicorn src.main:app --host 0.0.0.0 --port 8000

开发模式: 前端独立运行 (Vite dev server → localhost:5173)
生产模式: 前端构建产物由 FastAPI 直接托管
"""

from __future__ import annotations

import logging
import os
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
from starlette.responses import FileResponse, Response

from api.chat import router as agent_router
from auth.router import init_auth_mongo, router as auth_router
from deep_agent.graph import cleanup_all

# ---------------------------------------------------------------------------
# Logging 配置
# ---------------------------------------------------------------------------

def _configure_logging() -> None:
    """配置项目日志：开发环境人类可读，生产环境行式格式。"""
    fmt = (
        "[%(asctime)s] [%(levelname)-7s] [%(name)s] %(message)s"
    )
    datefmt = "%Y-%m-%d %H:%M:%S"

    # Root logger — 控制台输出
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if os.getenv("DEBUG") else logging.INFO)
    # 避免重复添加（uvicorn reload 会重新执行模块）
    if not root.handlers:
        root.addHandler(handler)

    # 抑制第三方库的 DEBUG 日志
    for noisy in ("httpx", "httpcore", "urllib3", "pymongo", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


_configure_logging()
logger = logging.getLogger("milo")

# 前端构建产物目录
_FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "client", "dist")


# ---------------------------------------------------------------------------
# App & lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期 —— 启动初始化 & 关闭时清理 sandbox。"""
    logger.info("MiloAgent 启动中...")

    try:
        mongo_client = MongoClient("mongodb://localhost:27017")
        init_auth_mongo(mongo_client)
        logger.info("MongoDB 用户集合已初始化")
    except Exception as e:
        logger.warning("无法连接 MongoDB 用于认证: %s", e)

    yield

    count = await cleanup_all()
    if count:
        logger.info("已清理 %s 个活跃线程 + sandbox", count)
    logger.info("MiloAgent 已关闭")


app = FastAPI(
    title="MiloAgent",
    version="0.1.0",
    description="Deep Agent — 兼容 LangGraph API 的独立部署服务",
    lifespan=lifespan,
)

# CORS —— 允许前端开发服务器跨域访问（生产环境无影响，因为前端同源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:
    start = time.monotonic()
    response = await call_next(request)
    elapsed = time.monotonic() - start
    logger.info(
        "%s %s → %s (%.0fms)",
        request.method, request.url.path, response.status_code, elapsed * 1000,
    )
    return response

# API 路由（先注册，优先匹配）
app.include_router(auth_router)
app.include_router(agent_router)

# ---------------------------------------------------------------------------
# 生产模式：托管前端静态资源
# ---------------------------------------------------------------------------
if os.path.isdir(_FRONTEND_DIST):
    assets_dir = os.path.join(_FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
        logger.info("已挂载前端静态资源: %s", _FRONTEND_DIST)

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        """SPA 回退 —— 非 API 路径返回 index.html，支持前端路由。"""
        index_path = os.path.join(_FRONTEND_DIST, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        return {"detail": "Not Found"}
else:
    logger.info("未检测到前端构建产物，仅提供 API 服务")
