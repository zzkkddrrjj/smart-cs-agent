"""
订单服务 - FastAPI 应用入口
"""

import os
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field

# 数据模型
class OrderItem(BaseModel):
    product_id: str
    name: str
    quantity: int
    price: float

class OrderDetail(BaseModel):
    order_id: str
    user_id: str
    status: str
    items: list[OrderItem]
    total_amount: float
    payment_method: str
    created_at: datetime
    shipped_at: Optional[datetime] = None

class CancelRequest(BaseModel):
    reason: str
    user_id: str

class CancelResult(BaseModel):
    order_id: str
    status: str
    refund_amount: float
    refund_eta: str

class RefundRequest(BaseModel):
    user_id: str
    reason: str
    refund_type: str = Field(default="full", pattern="^(full|partial)$")
    description: Optional[str] = None
    images: list[str] = []

class RefundResult(BaseModel):
    refund_id: str
    status: str
    estimated_time: str

# 响应格式
class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[dict] = None
    trace_id: Optional[str] = None

# 应用生命周期
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化
    print("订单服务启动中...")
    yield
    # 关闭时清理
    print("订单服务关闭")

app = FastAPI(
    title="订单服务",
    description="电商订单查询、取消、退款服务",
    version="1.0.0",
    lifespan=lifespan
)

# 模拟数据库
ORDERS_DB = {
    "ORD-001": OrderDetail(
        order_id="ORD-001",
        user_id="user_123",
        status="shipped",
        items=[
            OrderItem(product_id="P001", name="智能手机", quantity=1, price=2999.00),
        ],
        total_amount=2999.00,
        payment_method="alipay",
        created_at=datetime(2024, 1, 1, 10, 0, 0),
        shipped_at=datetime(2024, 1, 2, 14, 0, 0)
    ),
    "ORD-002": OrderDetail(
        order_id="ORD-002",
        user_id="user_456",
        status="delivered",
        items=[
            OrderItem(product_id="P002", name="蓝牙耳机", quantity=2, price=199.00),
        ],
        total_amount=398.00,
        payment_method="wechat",
        created_at=datetime(2024, 1, 3, 9, 0, 0),
        shipped_at=datetime(2024, 1, 4, 16, 0, 0)
    ),
}

@app.get("/api/v1/orders/{order_id}", response_model=ApiResponse)
async def query_order(order_id: str):
    """查询订单详情"""
    order = ORDERS_DB.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    return ApiResponse(
        code=0,
        message="success",
        data=order.model_dump()
    )

@app.post("/api/v1/orders/{order_id}/cancel", response_model=ApiResponse)
async def cancel_order(order_id: str, request: CancelRequest):
    """取消订单"""
    order = ORDERS_DB.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.user_id != request.user_id:
        raise HTTPException(status_code=403, detail="无权操作此订单")

    # 检查订单状态
    if order.status in ["cancelled", "delivered"]:
        raise HTTPException(
            status_code=400,
            detail=f"订单状态为 {order.status}，无法取消"
        )

    # 模拟取消操作
    result = CancelResult(
        order_id=order_id,
        status="cancelled",
        refund_amount=order.total_amount,
        refund_eta="3-5个工作日"
    )

    return ApiResponse(
        code=0,
        message="订单已取消",
        data=result.model_dump()
    )

@app.post("/api/v1/orders/{order_id}/refund", response_model=ApiResponse)
async def apply_refund(order_id: str, request: RefundRequest):
    """申请退款"""
    order = ORDERS_DB.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.user_id != request.user_id:
        raise HTTPException(status_code=403, detail="无权操作此订单")

    # 检查订单状态
    if order.status == "cancelled":
        raise HTTPException(status_code=400, detail="订单已取消")

    # 生成退款 ID
    import uuid
    refund_id = f"REF-{str(uuid.uuid4())[:8]}"

    # 计算退款金额
    refund_amount = order.total_amount
    if request.refund_type == "partial":
        refund_amount = order.total_amount * 0.5  # 示例：部分退款50%

    result = RefundResult(
        refund_id=refund_id,
        status="pending",
        estimated_time="1-3个工作日审核"
    )

    return ApiResponse(
        code=0,
        message="退款申请已提交",
        data=result.model_dump()
    )

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "order-service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
