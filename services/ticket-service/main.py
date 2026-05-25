"""
工单服务 - FastAPI 应用入口
"""

import os
import uuid
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# 数据模型
class TicketCreate(BaseModel):
    user_id: str
    session_id: Optional[str] = None
    category: str = Field(..., pattern="^(complaint|suggestion|technical|other)$")
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")
    description: str
    attachments: list[str] = []
    metadata: Optional[dict] = None

class TicketUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(open|in_progress|resolved|closed)$")
    assigned_to: Optional[str] = None
    note: Optional[str] = None

class TicketClose(BaseModel):
    resolution: str
    satisfaction: Optional[int] = Field(None, ge=1, le=5)

class Ticket(BaseModel):
    ticket_id: str
    user_id: str
    session_id: Optional[str]
    category: str
    priority: str
    status: str
    description: str
    attachments: list[str]
    metadata: Optional[dict]
    assigned_to: Optional[str]
    resolution: Optional[str]
    satisfaction: Optional[int]
    notes: list[dict]
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]

# 响应格式
class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[dict] = None
    trace_id: Optional[str] = None

# 应用生命周期
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("工单服务启动中...")
    yield
    print("工单服务关闭")

app = FastAPI(
    title="工单服务",
    description="工单创建、查询、更新、关闭服务",
    version="1.0.0",
    lifespan=lifespan
)

# 模拟数据库
TICKETS_DB = {}

@app.post("/api/v1/tickets", response_model=ApiResponse)
async def create_ticket(request: TicketCreate):
    """创建工单"""
    ticket_id = f"TKT-{str(uuid.uuid4())[:8]}"
    now = datetime.now()

    ticket = Ticket(
        ticket_id=ticket_id,
        user_id=request.user_id,
        session_id=request.session_id,
        category=request.category,
        priority=request.priority,
        status="open",
        description=request.description,
        attachments=request.attachments,
        metadata=request.metadata,
        assigned_to=None,
        resolution=None,
        satisfaction=None,
        notes=[],
        created_at=now,
        updated_at=now,
        resolved_at=None
    )

    TICKETS_DB[ticket_id] = ticket

    # 根据优先级估算响应时间
    response_time_map = {
        "low": "48小时内",
        "medium": "24小时内",
        "high": "4小时内",
        "urgent": "1小时内"
    }

    return ApiResponse(
        code=0,
        message="工单已创建",
        data={
            "ticket_id": ticket_id,
            "status": "open",
            "created_at": now.isoformat(),
            "estimated_response": response_time_map.get(request.priority, "24小时内")
        }
    )

@app.get("/api/v1/tickets/{ticket_id}", response_model=ApiResponse)
async def get_ticket(ticket_id: str):
    """查询工单"""
    ticket = TICKETS_DB.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")

    return ApiResponse(
        code=0,
        message="success",
        data=ticket.model_dump()
    )

@app.patch("/api/v1/tickets/{ticket_id}", response_model=ApiResponse)
async def update_ticket(ticket_id: str, request: TicketUpdate):
    """更新工单"""
    ticket = TICKETS_DB.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")

    now = datetime.now()

    if request.status:
        ticket.status = request.status
    if request.assigned_to:
        ticket.assigned_to = request.assigned_to
    if request.note:
        ticket.notes.append({
            "content": request.note,
            "timestamp": now.isoformat(),
            "by": "system"
        })

    ticket.updated_at = now

    return ApiResponse(
        code=0,
        message="工单已更新",
        data=ticket.model_dump()
    )

@app.post("/api/v1/tickets/{ticket_id}/close", response_model=ApiResponse)
async def close_ticket(ticket_id: str, request: TicketClose):
    """关闭工单"""
    ticket = TICKETS_DB.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")

    now = datetime.now()
    ticket.status = "closed"
    ticket.resolution = request.resolution
    ticket.satisfaction = request.satisfaction
    ticket.resolved_at = now
    ticket.updated_at = now

    return ApiResponse(
        code=0,
        message="工单已关闭",
        data=ticket.model_dump()
    )

@app.post("/api/v1/tickets/{ticket_id}/escalate", response_model=ApiResponse)
async def escalate_ticket(ticket_id: str, reason: str):
    """升级工单"""
    ticket = TICKETS_DB.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")

    now = datetime.now()
    ticket.priority = "urgent"
    ticket.notes.append({
        "content": f"工单升级: {reason}",
        "timestamp": now.isoformat(),
        "by": "system"
    })
    ticket.updated_at = now

    return ApiResponse(
        code=0,
        message="工单已升级",
        data=ticket.model_dump()
    )

@app.get("/api/v1/tickets", response_model=ApiResponse)
async def list_tickets(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None
):
    """查询工单列表"""
    tickets = list(TICKETS_DB.values())

    if user_id:
        tickets = [t for t in tickets if t.user_id == user_id]
    if status:
        tickets = [t for t in tickets if t.status == status]
    if category:
        tickets = [t for t in tickets if t.category == category]

    return ApiResponse(
        code=0,
        message="success",
        data={
            "total": len(tickets),
            "tickets": [t.model_dump() for t in tickets]
        }
    )

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "ticket-service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
