"""MiloAgent API —— 兼容 LangGraph 标准接口。

端点设计对齐 langgraph dev：
  - /threads             线程 CRUD（与 user_id 绑定）
  - /threads/{id}/runs   运行 & 流式
  - /threads/{id}/state  状态读写
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from langchain_core.messages import AIMessageChunk, HumanMessage, ToolMessage
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

import asyncio

from auth.dependencies import get_current_user
from deep_agent.graph import (
    cleanup_thread,
    get_or_create_agent,
    get_thread_meta,
    list_threads_by_user,
    new_thread_id,
    save_thread_meta,
)
from deep_agent.opensandbox_backend import get_or_create_sandbox

router = APIRouter(prefix="/api", tags=["LangGraph API"])


# =============================================================================
# 辅助函数 —— user_id 所有权校验
# =============================================================================

async def _get_owner_meta(thread_id: str) -> dict:
    """获取线程元数据，若不存在抛出 404。"""
    meta = await get_thread_meta(thread_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"线程 {thread_id} 不存在")
    return meta


async def _require_owner(thread_id: str, user_id: str) -> dict:
    """校验线程归属于指定用户，否则 403。返回元数据。"""
    meta = await _get_owner_meta(thread_id)
    owner = meta.get("user_id", "")
    if owner != user_id:
        raise HTTPException(
            status_code=403,
            detail=f"线程 {thread_id} 不属于用户 {user_id}",
        )
    return meta


# =============================================================================
# Pydantic models
# =============================================================================

class Message(BaseModel):
    role: str = Field(..., description="消息角色: user / assistant / system")
    content: str = Field(..., description="消息内容")


class CreateThreadRequest(BaseModel):
    metadata: dict[str, Any] | None = Field(default=None, description="线程元数据（可选）")


class ThreadInfo(BaseModel):
    thread_id: str
    user_id: str
    created_at: str
    metadata: dict[str, Any] | None


class CreateRunRequest(BaseModel):
    messages: list[Message] = Field(..., description="本轮用户输入的消息")
    stream: bool = Field(default=False, description="是否流式返回")


class RunResult(BaseModel):
    thread_id: str
    user_id: str
    messages: list[dict[str, Any]]
    status: str = "completed"


class StateResponse(BaseModel):
    thread_id: str
    user_id: str
    values: dict[str, Any]


# =============================================================================
# Thread CRUD（与 user_id 绑定）
# =============================================================================

@router.post("/threads", summary="创建新线程")
async def create_thread(
    body: CreateThreadRequest,
    current_user: dict = Depends(get_current_user),
) -> ThreadInfo:
    """创建一个新的对话线程，绑定到当前认证用户。

    线程元数据写入 MongoDB 持久化。同时在后台预创建 sandbox。
    """
    user_id = current_user["user_id"]
    # 后台预创建 sandbox（fire-and-forget）
    asyncio.create_task(get_or_create_sandbox(user_id))
    thread_id = new_thread_id()
    await save_thread_meta(thread_id, user_id=user_id, metadata=body.metadata)
    meta = await _get_owner_meta(thread_id)
    return _meta_to_info(meta)


@router.get("/threads", summary="列出用户线程")
async def list_threads(
    current_user: dict = Depends(get_current_user),
) -> list[ThreadInfo]:
    """返回当前认证用户的所有线程（从 MongoDB 读取，重启不丢失）。

    同时在后台预创建 sandbox，使后续的 state/runs 请求无需等待 sandbox 创建。
    """
    user_id = current_user["user_id"]
    # 后台预创建 sandbox（fire-and-forget），不阻塞线程列表响应
    asyncio.create_task(get_or_create_sandbox(user_id))
    try:
        threads = await list_threads_by_user(user_id)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"无法连接 MongoDB，请确认 MongoDB 服务已启动: {e}")
    return [_meta_to_info(t) for t in threads]


@router.get("/threads/{thread_id}", summary="查询线程信息")
async def get_thread(
    thread_id: str,
    current_user: dict = Depends(get_current_user),
) -> ThreadInfo:
    """获取指定线程的元数据。需校验线程归属。"""
    user_id = current_user["user_id"]
    meta = await _require_owner(thread_id, user_id)
    return _meta_to_info(meta)


@router.delete("/threads/{thread_id}", summary="删除线程")
async def delete_thread(
    thread_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """删除线程。需校验线程归属（沙盒按用户共享，不会销毁）。"""
    user_id = current_user["user_id"]
    await _require_owner(thread_id, user_id)
    ok = await cleanup_thread(thread_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"线程 {thread_id} 不存在或已销毁")
    return {"status": "deleted", "thread_id": thread_id}


# =============================================================================
# Runs（非流式 & 流式）
# =============================================================================

@router.post("/threads/{thread_id}/runs", summary="非流式运行 agent")
async def run_agent(
    thread_id: str,
    body: CreateRunRequest,
    current_user: dict = Depends(get_current_user),
) -> RunResult:
    """向指定线程发送消息，等待 agent 完整执行后返回结果。"""
    user_id = current_user["user_id"]
    # 校验线程归属
    await _require_owner(thread_id, user_id)

    lc_messages = [HumanMessage(content=m.content) for m in body.messages if m.role == "user"]
    if not lc_messages:
        raise HTTPException(status_code=400, detail="至少需要一条 role=user 的消息")

    config = {"configurable": {"thread_id": thread_id, "user_id": user_id}}

    try:
        agent = await get_or_create_agent(thread_id, user_id=user_id)
        result = await agent.ainvoke({"messages": lc_messages}, config=config)

        output_messages = []
        for msg in result.get("messages", []):
            msg_dict = {"role": msg.type, "content": msg.content}
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                msg_dict["tool_calls"] = [
                    {"name": tc.get("name"), "args": tc.get("args")}
                    for tc in msg.tool_calls
                ]
            output_messages.append(msg_dict)

        return RunResult(thread_id=thread_id, user_id=user_id, messages=output_messages)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/threads/{thread_id}/runs/stream", summary="流式运行 agent (SSE)")
async def run_agent_stream(
    thread_id: str,
    body: CreateRunRequest,
    current_user: dict = Depends(get_current_user),
):
    """向指定线程发送消息，以 SSE 流式返回 agent 的思考/工具调用/最终输出。"""
    user_id = current_user["user_id"]
    await _require_owner(thread_id, user_id)

    lc_messages = [HumanMessage(content=m.content) for m in body.messages if m.role == "user"]
    if not lc_messages:
        raise HTTPException(status_code=400, detail="至少需要一条 role=user 的消息")

    config = {"configurable": {"thread_id": thread_id, "user_id": user_id}}

    async def event_stream():
        try:
            agent = await get_or_create_agent(thread_id, user_id=user_id)

            async for chunk in agent.astream(
                {"messages": lc_messages},
                config=config,
                stream_mode="messages",
            ):
                msg_chunk = chunk[0]

                # --- Tool result (ToolMessage) ---
                if isinstance(msg_chunk, ToolMessage):
                    event = {
                        "type": "tool_result",
                        "tool_call_id": getattr(msg_chunk, "tool_call_id", ""),
                        "name": getattr(msg_chunk, "name", ""),
                        "content": msg_chunk.content,
                    }
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    continue

                # --- AI text / tool call request ---
                event: dict[str, Any] = {"type": "message"}

                if isinstance(msg_chunk, AIMessageChunk) and msg_chunk.content:
                    event["content"] = msg_chunk.content

                if hasattr(msg_chunk, "tool_calls") and msg_chunk.tool_calls:
                    event["tool_calls"] = [
                        {"name": tc.get("name"), "args": tc.get("args"),
                         "id": tc.get("id") or f"{tc.get('name')}_{tc.get('index', i)}"}
                        for i, tc in enumerate(msg_chunk.tool_calls)
                    ]

                if hasattr(msg_chunk, "tool_call_chunks") and msg_chunk.tool_call_chunks:
                    event["tool_call_chunks"] = [
                        {"name": c.get("name", ""), "content": c.get("args", ""),
                         "id": c.get("id") or f"{c.get('name', '')}_{c.get('index', '')}"}
                        for c in msg_chunk.tool_call_chunks
                    ]

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'thread_id': thread_id}, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# =============================================================================
# State（读取线程状态）
# =============================================================================

@router.get("/threads/{thread_id}/state", summary="读取线程状态")
async def get_state(
    thread_id: str,
    current_user: dict = Depends(get_current_user),
) -> StateResponse:
    """获取指定线程的当前状态（消息历史、变量等）。

    线程元数据从 MongoDB 验证归属，状态从 MongoDB checkpoint 读取。
    """
    user_id = current_user["user_id"]
    await _require_owner(thread_id, user_id)

    config = {"configurable": {"thread_id": thread_id, "user_id": user_id}}

    try:
        agent = await get_or_create_agent(thread_id, user_id=user_id)
        state = await agent.aget_state(config)
        values = state.values if state.values else {}
        return StateResponse(thread_id=thread_id, user_id=user_id, values=values)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Helpers
# =============================================================================

def _meta_to_info(meta: dict) -> ThreadInfo:
    """将线程元数据 dict 转为 ThreadInfo 模型。"""
    return ThreadInfo(
        thread_id=meta.get("thread_id", ""),
        user_id=meta.get("user_id", ""),
        created_at=meta.get("created_at", ""),
        metadata=json.loads(meta["metadata"]) if meta.get("metadata") else None,
    )
