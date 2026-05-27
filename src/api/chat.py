import json
from typing import List, Dict, Any, Optional

from fastapi import APIRouter
from fastapi.params import Depends
from langchain_core.messages import HumanMessage, AIMessageChunk
from langchain_core.runnables import RunnableConfig
from langgraph_sdk.runtime import ServerRuntime
from pydantic import BaseModel
from starlette.responses import StreamingResponse
from deep_agent.graph import  build_agent

api = APIRouter(prefix='/api',tags=["agent的聊天接口"])

class ChatRequest(BaseModel):
    messages:List[Dict[str,Any]]
    thread_id:Optional[str] = "default_tread_id"

class ChatResponse(BaseModel):
    success:bool
    data:str


#非流式接口
@api.post("/chat",response_model=ChatResponse,summary="非流式聊天接口")
async def chat_endpoint(request:ChatRequest):
    try:
        #将请求消息转换为LangChain的消息对象
        messages = [HumanMessage(content=msg["content"]) for msg in request.messages if msg["role"]=="user"]
        config = {"configurable":{"thread_id":request.thread_id}}
        agent = build_agent(config)
        result = await agent.ainvoke({"messages": messages}, config=config)
        # 提取最终的文本输出信息
        final_output = result["messages"][-1].content
        return ChatResponse(success=True, data=final_output)
    except Exception as e:
        return ChatResponse(success=False,data=str(e))
#流式接口：实时返回Agent的思考、工具调用和最终接口
@api.post("/chat/stream",summary="流式聊天接口")
async def chat_steam_endpoint(request:ChatRequest):
    async def generate_stream():
        try:
            messages = [HumanMessage(content=msg["content"]) for msg in request.messages if msg["role"]=="user"]
            config = {"configurable":{"thread_id":request.thread_id}}

            agent = build_agent(config)
            async for chunk in agent.astream({"messages": messages}, config=config, stream_mode="messages"):
                # 过滤并返回AI生成的文本内容片段
                if isinstance(chunk[0], AIMessageChunk) and chunk[0].content:
                    # 按照SSE（Sever Sent Events)协议格式返回
                    yield f"data:{json.dumps({'content': chunk[0].content}, ensure_ascii=False)}\n\n"

            # 结束流
            yield "data:[DONE]\n\n"
        except Exception as e:
            yield f"data:{json.dumps({'error':str(e)},ensure_ascii=False)}\n\n"
    return StreamingResponse(generate_stream(), media_type="text/event-stream")


