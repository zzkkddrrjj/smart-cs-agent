"""
知识库服务 - FastAPI 应用入口
"""

import os
import uuid
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# 数据模型
class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    filters: Optional[dict] = None

class SearchResultItem(BaseModel):
    id: str
    content: str
    score: float
    metadata: dict

class DocumentCreate(BaseModel):
    content: str
    metadata: Optional[dict] = None

class DocumentUpdate(BaseModel):
    content: str
    metadata: Optional[dict] = None

# 响应格式
class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[dict] = None
    trace_id: Optional[str] = None

# 应用生命周期
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("知识库服务启动中...")
    yield
    print("知识库服务关闭")

app = FastAPI(
    title="知识库服务",
    description="知识库检索、管理服务",
    version="1.0.0",
    lifespan=lifespan
)

# 模拟知识库
KNOWLEDGE_DB = {
    "doc_001": {
        "id": "doc_001",
        "content": "退货政策：自签收之日起7天内，商品未使用、包装完好的情况下可申请无理由退货。退货运费由买家承担，除非商品存在质量问题。",
        "metadata": {"source": "help_center", "category": "return_policy", "updated_at": "2024-01-01"},
        "tenant_id": "default"
    },
    "doc_002": {
        "id": "doc_002",
        "content": "退款时效：退款申请提交后，1-3个工作日内审核。审核通过后，退款将在3-5个工作日内原路返回到您的支付账户。",
        "metadata": {"source": "help_center", "category": "refund_policy", "updated_at": "2024-01-01"},
        "tenant_id": "default"
    },
    "doc_003": {
        "id": "doc_003",
        "content": "配送时效：普通快递3-5个工作日到达，偏远地区可能需要5-7个工作日。顺丰快递1-3个工作日到达。",
        "metadata": {"source": "help_center", "category": "delivery_policy", "updated_at": "2024-01-01"},
        "tenant_id": "default"
    },
    "doc_004": {
        "id": "doc_004",
        "content": "发票服务：订单完成后可申请电子发票，在订单详情页点击"申请发票"即可。纸质发票需联系客服，运费由买家承担。",
        "metadata": {"source": "help_center", "category": "invoice_policy", "updated_at": "2024-01-01"},
        "tenant_id": "default"
    },
}

@app.post("/api/v1/knowledge/search", response_model=ApiResponse)
async def search_knowledge(request: SearchRequest):
    """检索知识库"""
    # 简单的关键词匹配模拟（实际应使用向量检索）
    query_lower = request.query.lower()
    results = []

    for doc_id, doc in KNOWLEDGE_DB.items():
        content = doc["content"].lower()
        # 简单匹配
        if any(word in content for word in query_lower.split()):
            score = 0.8  # 模拟分数
            results.append(SearchResultItem(
                id=doc_id,
                content=doc["content"],
                score=score,
                metadata=doc["metadata"]
            ))

    # 按分数排序
    results.sort(key=lambda x: x.score, reverse=True)
    results = results[:request.top_k]

    return ApiResponse(
        code=0,
        message="success",
        data={
            "results": [r.model_dump() for r in results]
        }
    )

@app.post("/api/v1/knowledge/documents", response_model=ApiResponse)
async def add_document(request: DocumentCreate, tenant_id: str = "default"):
    """添加知识文档"""
    doc_id = f"doc_{str(uuid.uuid4())[:8]}"

    KNOWLEDGE_DB[doc_id] = {
        "id": doc_id,
        "content": request.content,
        "metadata": request.metadata or {},
        "tenant_id": tenant_id
    }

    return ApiResponse(
        code=0,
        message="文档已添加",
        data={"id": doc_id}
    )

@app.put("/api/v1/knowledge/documents/{doc_id}", response_model=ApiResponse)
async def update_document(doc_id: str, request: DocumentUpdate):
    """更新知识文档"""
    if doc_id not in KNOWLEDGE_DB:
        raise HTTPException(status_code=404, detail="文档不存在")

    KNOWLEDGE_DB[doc_id]["content"] = request.content
    if request.metadata:
        KNOWLEDGE_DB[doc_id]["metadata"].update(request.metadata)

    return ApiResponse(
        code=0,
        message="文档已更新",
        data={"id": doc_id}
    )

@app.delete("/api/v1/knowledge/documents/{doc_id}", response_model=ApiResponse)
async def delete_document(doc_id: str):
    """删除知识文档"""
    if doc_id not in KNOWLEDGE_DB:
        raise HTTPException(status_code=404, detail="文档不存在")

    del KNOWLEDGE_DB[doc_id]

    return ApiResponse(
        code=0,
        message="文档已删除",
        data={"id": doc_id}
    )

@app.get("/api/v1/knowledge/documents/{doc_id}", response_model=ApiResponse)
async def get_document(doc_id: str):
    """查询知识文档"""
    if doc_id not in KNOWLEDGE_DB:
        raise HTTPException(status_code=404, detail="文档不存在")

    return ApiResponse(
        code=0,
        message="success",
        data=KNOWLEDGE_DB[doc_id]
    )

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "knowledge-service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
