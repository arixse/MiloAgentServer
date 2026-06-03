"""MiloAgent — FastAPI 入口。

启动:  uvicorn src.main:app --host 0.0.0.0 --port 8000

开发模式: 前端独立运行 (Vite dev server → localhost:5173)
生产模式: 前端构建产物由 FastAPI 直接托管
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
from starlette.responses import FileResponse

from api.chat import router as agent_router
from auth.router import init_auth_mongo, router as auth_router
from deep_agent.graph import cleanup_all

# 前端构建产物目录（Docker 构建时写入，开发时可能不存在）
_FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "client", "dist")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期 —— 启动初始化 & 关闭时清理 sandbox。"""
    print("[Server] MiloAgent 启动中...")

    # 初始化 MongoDB 用户集合（用于认证）
    try:
        mongo_client = MongoClient("mongodb://localhost:27017")
        init_auth_mongo(mongo_client)
    except Exception as e:
        print(f"[Server] 警告: 无法连接 MongoDB 用于认证 —— {e}")

    yield
    # Shutdown: 清理所有活跃的 sandbox
    count = await cleanup_all()
    if count:
        print(f"[Server] 已清理 {count} 个活跃 sandbox")
    print("[Server] MiloAgent 已关闭")


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
        print(f"[Server] 已挂载前端静态资源: {_FRONTEND_DIST}")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        """SPA 回退 —— 非 API 路径返回 index.html，支持前端路由。"""
        index_path = os.path.join(_FRONTEND_DIST, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        return {"detail": "Not Found"}
else:
    print("[Server] 未检测到前端构建产物，仅提供 API 服务")
