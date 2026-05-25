"""
网关服务 - 消息接入与对话接口
"""

import os
import uuid
import json
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# 数据模型
class MessageContent(BaseModel):
    type: str = "text"
    text: Optional[str] = None
    images: list[str] = []

class MessageRequest(BaseModel):
    channel: str
    user_id: str
    message_id: Optional[str] = None
    content: MessageContent
    metadata: Optional[dict] = None

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    user_id: str
    message: str
    context: Optional[dict] = None

class ReplyRequest(BaseModel):
    session_id: str
    channel: str
    content: MessageContent
    metadata: Optional[dict] = None

class TransferRequest(BaseModel):
    session_id: str
    reason: str
    context: Optional[dict] = None

# 响应格式
class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[dict] = None
    trace_id: Optional[str] = None

# 会话存储（内存模拟，生产用 Redis）
sessions: dict[str, dict] = {}

# 应用生命周期
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("网关服务启动中...")
    yield
    print("网关服务关闭")

app = FastAPI(
    title="网关服务",
    description="消息接入与对话接口",
    version="1.0.0",
    lifespan=lifespan
)

@app.post("/api/v1/gateway/message", response_model=ApiResponse)
async def receive_message(request: MessageRequest):
    """接收渠道消息"""
    session_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())

    # 创建或获取会话
    session = {
        "session_id": session_id,
        "user_id": request.user_id,
        "channel": request.channel,
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "messages": []
    }
    sessions[session_id] = session

    # 记录用户消息
    session["messages"].append({
        "role": "user",
        "content": request.content.text,
        "timestamp": datetime.now().isoformat()
    })

    return ApiResponse(
        code=0,
        message="success",
        data={
            "session_id": session_id,
            "accepted": True
        },
        trace_id=trace_id
    )

@app.post("/api/v1/chat/completions", response_model=ApiResponse)
async def chat_completions(request: ChatRequest):
    """对话接口（非流式）"""
    trace_id = str(uuid.uuid4())
    session_id = request.session_id or str(uuid.uuid4())

    # 获取或创建会话
    if session_id not in sessions:
        sessions[session_id] = {
            "session_id": session_id,
            "user_id": request.user_id,
            "channel": request.context.get("channel", "api") if request.context else "api",
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "messages": []
        }

    session = sessions[session_id]

    # 记录用户消息
    session["messages"].append({
        "role": "user",
        "content": request.message,
        "timestamp": datetime.now().isoformat()
    })

    # 调用 Agent（模拟，实际调用 Dify API）
    intent = _classify_intent(request.message)
    reply = _generate_reply(request.message, intent, session)

    # 记录助手回复
    session["messages"].append({
        "role": "assistant",
        "content": reply,
        "timestamp": datetime.now().isoformat()
    })

    return ApiResponse(
        code=0,
        message="success",
        data={
            "session_id": session_id,
            "reply": reply,
            "intent": intent,
            "confidence": 0.9,
            "tool_calls": [],
            "metadata": {
                "model": "mock",
                "tokens_used": 150,
                "latency_ms": 800
            }
        },
        trace_id=trace_id
    )

@app.post("/api/v1/chat/stream")
async def chat_stream(request: ChatRequest):
    """对话接口（流式 SSE）"""
    session_id = request.session_id or str(uuid.uuid4())
    intent = _classify_intent(request.message)

    async def event_generator():
        # 思考阶段
        yield f"data: {json.dumps({'type': 'thinking', 'content': '正在分析您的问题...'})}\n\n"

        # 意图识别结果
        yield f"data: {json.dumps({'type': 'intent', 'content': intent})}\n\n"

        # 模拟回复生成
        reply = _generate_reply(request.message, intent, {"messages": []})
        words = reply.split(" ")
        for i in range(0, len(words), 3):
            chunk = " ".join(words[i:i+3])
            yield f"data: {json.dumps({'type': 'reply', 'content': chunk})}\n\n"

        # 完成
        yield f"data: {json.dumps({'type': 'done', 'metadata': {'session_id': session_id}})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )

@app.post("/api/v1/gateway/reply", response_model=ApiResponse)
async def send_reply(request: ReplyRequest):
    """发送回复到渠道"""
    session = sessions.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 记录回复
    session["messages"].append({
        "role": "assistant",
        "content": request.content.text,
        "timestamp": datetime.now().isoformat()
    })

    return ApiResponse(
        code=0,
        message="回复已发送",
        data={"session_id": request.session_id}
    )

@app.post("/api/v1/gateway/transfer", response_model=ApiResponse)
async def transfer_to_human(request: TransferRequest):
    """转人工"""
    session = sessions.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    session["status"] = "transferred"

    return ApiResponse(
        code=0,
        message="转人工成功",
        data={
            "transfer_id": str(uuid.uuid4()),
            "status": "queued",
            "queue_position": 3,
            "estimated_wait_time": "5分钟"
        }
    )

@app.get("/api/v1/gateway/sessions/{session_id}", response_model=ApiResponse)
async def get_session(session_id: str):
    """获取会话信息"""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    return ApiResponse(
        code=0,
        message="success",
        data=session
    )

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "gateway"}

def _classify_intent(message: str) -> str:
    """简单意图分类（模拟）"""
    message = message.lower()
    if any(kw in message for kw in ["订单", "ord", "下单"]):
        return "order_query"
    elif any(kw in message for kw in ["快递", "物流", "到哪", "发货"]):
        return "logistics_query"
    elif any(kw in message for kw in ["退货", "退款", "换货", "退"]):
        return "return_goods"
    elif any(kw in message for kw in ["投诉", "差评", "不满", "举报"]):
        return "complaint"
    elif any(kw in message for kw in ["转人工", "找客服", "真人", "人工"]):
        return "human_transfer"
    elif any(kw in message for kw in ["你好", "hi", "hello", "在吗"]):
        return "greeting"
    else:
        return "other"

def _generate_reply(message: str, intent: str, session: dict) -> str:
    """生成回复（模拟，实际调用 LLM）"""
    replies = {
        "order_query": "好的，请提供您的订单号，我帮您查询订单状态。",
        "logistics_query": "请提供您的快递单号或订单号，我帮您查询物流信息。",
        "return_goods": "好的，请提供您的订单号，我帮您查看退货流程和条件。",
        "complaint": "非常抱歉给您带来不好的体验。请提供订单号和具体问题，我立即为您处理。",
        "human_transfer": "好的，我现在就帮您转接人工客服。请稍等片刻。",
        "greeting": "您好！我是智能客服小助手，很高兴为您服务。请问有什么可以帮您的？",
        "other": "这个问题我需要帮您确认一下，请稍等。您也可以尝试描述更具体的问题，或者转接人工客服。"
    }
    return replies.get(intent, "请问有什么可以帮您的？")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
