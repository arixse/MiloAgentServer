"""MiloAgent — FastAPI 入口。

启动:  uvicorn src.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.chat import router as agent_router
from deep_agent.graph import cleanup_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期 —— 启动初始化 & 关闭时清理 sandbox。"""
    print("[Server] MiloAgent 启动中...")
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

app.include_router(agent_router)
