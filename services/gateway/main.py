"""
网关服务 - 消息接入与对话接口
"""

import os
import sys
import uuid
import json
import time
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm_client import get_llm_client

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

    # 调用 LLM
    intent = _classify_intent(request.message)
    start_time = time.time()

    try:
        llm = get_llm_client()
        system_prompt = _build_system_prompt(intent, session)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.message}
        ]
        reply = llm.chat(messages)
        latency_ms = int((time.time() - start_time) * 1000)
    except Exception as e:
        reply = _generate_reply(request.message, intent, session)
        latency_ms = int((time.time() - start_time) * 1000)

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
                "model": os.getenv("LLM_MODEL", "mimo"),
                "latency_ms": latency_ms
            }
        },
        trace_id=trace_id
    )

@app.post("/api/v1/chat/stream")
async def chat_stream(request: ChatRequest):
    """对话接口（流式 SSE）"""
    session_id = request.session_id or str(uuid.uuid4())
    intent = _classify_intent(request.message)

    try:
        llm = get_llm_client()
        system_prompt = _build_system_prompt(intent, {"messages": []})
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.message}
        ]

        async def event_generator():
            yield f"data: {json.dumps({'type': 'thinking', 'content': '正在分析您的问题...'})}\n\n"
            yield f"data: {json.dumps({'type': 'intent', 'content': intent})}\n\n"

            for chunk in llm.chat_stream(messages):
                yield f"data: {json.dumps({'type': 'reply', 'content': chunk})}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'metadata': {'session_id': session_id}})}\n\n"

    except Exception as e:
        async def event_generator():
            reply = _generate_reply(request.message, intent, {"messages": []})
            yield f"data: {json.dumps({'type': 'reply', 'content': reply})}\n\n"
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
    """生成回复（兜底，LLM 调用失败时使用）"""
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

def _build_system_prompt(intent: str, session: dict) -> str:
    """构建 System Prompt"""
    base = """你是一个专业的电商客服助手，名叫"小助手"。

核心原则：
1. 专业准确：基于已知信息回答，不编造
2. 简洁高效：直接回答，避免废话
3. 温暖友好：态度亲切但不过度热情
4. 诚实守信：做不到的不承诺

禁止事项：
- 不要编造不存在的订单、物流、政策信息
- 不要承诺做不到的退款金额或时间
- 不要泄露公司内部信息"""

    intent_prompts = {
        "order_query": "\n\n当前场景：用户查询订单。请引导用户提供订单号，然后给出清晰的订单状态说明。",
        "logistics_query": "\n\n当前场景：用户查询物流。请引导用户提供快递单号，说明当前位置和预计到达时间。",
        "return_goods": "\n\n当前场景：用户要退换货。请引导用户提供订单号，说明退货流程和条件。",
        "complaint": "\n\n当前场景：用户投诉。请先安抚情绪，再收集信息，提出解决方案。",
        "human_transfer": "\n\n当前场景：用户要求转人工。请确认并告知正在转接。",
        "greeting": "\n\n当前场景：用户打招呼。请简短友好地回复。",
    }

    return base + intent_prompts.get(intent, "\n\n请根据用户问题给出准确回答。")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
