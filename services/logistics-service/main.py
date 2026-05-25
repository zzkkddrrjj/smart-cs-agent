"""
物流服务 - FastAPI 应用入口
"""

import os
from datetime import datetime, timedelta
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 数据模型
class TrackDetail(BaseModel):
    time: datetime
    location: str
    description: str

class LogisticsInfo(BaseModel):
    tracking_number: str
    carrier: str
    status: str
    estimated_delivery: Optional[datetime] = None
    current_location: str
    tracks: list[TrackDetail]

class UrgeRequest(BaseModel):
    order_id: str
    user_id: str
    reason: Optional[str] = None

class UrgeResult(BaseModel):
    urge_id: str
    status: str
    estimated_response: str

class InterceptRequest(BaseModel):
    order_id: str
    reason: str

class InterceptResult(BaseModel):
    intercept_id: str
    status: str
    message: str

# 响应格式
class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[dict] = None
    trace_id: Optional[str] = None

# 应用生命周期
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("物流服务启动中...")
    yield
    print("物流服务关闭")

app = FastAPI(
    title="物流服务",
    description="物流查询、催件、拦截服务",
    version="1.0.0",
    lifespan=lifespan
)

# 模拟数据库
LOGISTICS_DB = {
    "SF1234567890": LogisticsInfo(
        tracking_number="SF1234567890",
        carrier="顺丰速运",
        status="in_transit",
        estimated_delivery=datetime(2024, 1, 5),
        current_location="北京转运中心",
        tracks=[
            TrackDetail(
                time=datetime(2024, 1, 3, 10, 0, 0),
                location="北京转运中心",
                description="已发出"
            ),
            TrackDetail(
                time=datetime(2024, 1, 2, 18, 0, 0),
                location="上海仓库",
                description="已揽收"
            ),
        ]
    ),
    "YT9876543210": LogisticsInfo(
        tracking_number="YT9876543210",
        carrier="圆通速递",
        status="delivered",
        estimated_delivery=datetime(2024, 1, 4),
        current_location="已签收",
        tracks=[
            TrackDetail(
                time=datetime(2024, 1, 4, 14, 30, 0),
                location="北京市朝阳区",
                description="已签收，签收人：本人"
            ),
            TrackDetail(
                time=datetime(2024, 1, 4, 9, 0, 0),
                location="北京朝阳营业部",
                description="派件中"
            ),
            TrackDetail(
                time=datetime(2024, 1, 3, 20, 0, 0),
                location="北京转运中心",
                description="已到达"
            ),
        ]
    ),
}

@app.get("/api/v1/logistics/track/{tracking_number}", response_model=ApiResponse)
async def track_logistics(tracking_number: str):
    """查询物流信息"""
    logistics = LOGISTICS_DB.get(tracking_number)
    if not logistics:
        raise HTTPException(status_code=404, detail="快递单号不存在")

    return ApiResponse(
        code=0,
        message="success",
        data=logistics.model_dump()
    )

@app.post("/api/v1/logistics/urge", response_model=ApiResponse)
async def urge_delivery(request: UrgeRequest):
    """催件"""
    import uuid
    urge_id = f"URGE-{str(uuid.uuid4())[:8]}"

    result = UrgeResult(
        urge_id=urge_id,
        status="processing",
        estimated_response="24小时内"
    )

    return ApiResponse(
        code=0,
        message="催件申请已提交",
        data=result.model_dump()
    )

@app.post("/api/v1/logistics/intercept", response_model=ApiResponse)
async def intercept_package(request: InterceptRequest):
    """拦截包裹"""
    import uuid
    intercept_id = f"INT-{str(uuid.uuid4())[:8]}"

    result = InterceptResult(
        intercept_id=intercept_id,
        status="processing",
        message="包裹拦截申请已提交，预计1-2个工作日处理"
    )

    return ApiResponse(
        code=0,
        message="拦截申请已提交",
        data=result.model_dump()
    )

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "logistics-service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
