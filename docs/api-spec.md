# API 接口规范

## 1. 通用规范

### 1.1 基础约定

- **协议**: HTTPS
- **格式**: JSON
- **字符集**: UTF-8
- **时间格式**: ISO 8601（`2024-01-01T00:00:00Z`）

### 1.2 统一响应格式

```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "trace_id": "abc123"
}
```

**错误码分层**：

| 前缀 | 服务 | 示例 |
|------|------|------|
| 10xxx | 网关层 | 10001 参数错误 |
| 20xxx | 订单服务 | 20001 订单不存在 |
| 30xxx | 物流服务 | 30001 快递单号无效 |
| 40xxx | 工单服务 | 40001 工单创建失败 |
| 50xxx | 知识库服务 | 50001 检索失败 |
| 90xxx | 系统错误 | 90001 内部错误 |

### 1.3 认证方式

- **内部服务**: mTLS + Service Token
- **外部渠道**: API Key + HMAC 签名
- **用户态**: JWT Token（从渠道方获取）

### 1.4 限流策略

- 单用户：5 QPS
- 单 IP：50 QPS
- 全局：可配置

---

## 2. 网关接口 (Gateway)

### 2.1 接收消息

```
POST /api/v1/gateway/message
```

**请求**：

```json
{
  "channel": "feishu",
  "user_id": "user_123",
  "message_id": "msg_456",
  "content": {
    "type": "text",
    "text": "我要退货"
  },
  "metadata": {
    "nickname": "张三",
    "avatar": "https://...",
    "channel_user_id": "ou_xxx"
  }
}
```

**响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "session_id": "sess_789",
    "accepted": true
  }
}
```

### 2.2 发送回复

```
POST /api/v1/gateway/reply
```

**请求**：

```json
{
  "session_id": "sess_789",
  "channel": "feishu",
  "content": {
    "type": "text",
    "text": "好的，请提供您的订单号，我帮您查询退货流程。"
  },
  "metadata": {
    "reply_to": "msg_456"
  }
}
```

### 2.3 转人工

```
POST /api/v1/gateway/transfer
```

**请求**：

```json
{
  "session_id": "sess_789",
  "reason": "user_request",
  "context": {
    "summary": "用户要求退货，已查询订单 ORD-001",
    "messages": [...]
  }
}
```

---

## 3. 订单服务 (Order Service)

### 3.1 查询订单

```
GET /api/v1/orders/{order_id}
```

**响应**：

```json
{
  "code": 0,
  "data": {
    "order_id": "ORD-001",
    "user_id": "user_123",
    "status": "shipped",
    "items": [
      {
        "product_id": "P001",
        "name": "商品名称",
        "quantity": 1,
        "price": 99.00
      }
    ],
    "total_amount": 99.00,
    "payment_method": "alipay",
    "created_at": "2024-01-01T10:00:00Z",
    "shipped_at": "2024-01-02T14:00:00Z"
  }
}
```

### 3.2 取消订单

```
POST /api/v1/orders/{order_id}/cancel
```

**请求**：

```json
{
  "reason": "不想要了",
  "user_id": "user_123"
}
```

**响应**：

```json
{
  "code": 0,
  "data": {
    "order_id": "ORD-001",
    "status": "cancelled",
    "refund_amount": 99.00,
    "refund_eta": "3-5个工作日"
  }
}
```

### 3.3 申请退款

```
POST /api/v1/orders/{order_id}/refund
```

**请求**：

```json
{
  "user_id": "user_123",
  "reason": "商品质量问题",
  "refund_type": "full",
  "description": "收到的商品有破损",
  "images": ["https://..."]
}
```

**响应**：

```json
{
  "code": 0,
  "data": {
    "refund_id": "REF-001",
    "status": "pending",
    "estimated_time": "1-3个工作日审核"
  }
}
```

---

## 4. 物流服务 (Logistics Service)

### 4.1 查询物流

```
GET /api/v1/logistics/track/{tracking_number}
```

**响应**：

```json
{
  "code": 0,
  "data": {
    "tracking_number": "SF1234567890",
    "carrier": "顺丰速运",
    "status": "in_transit",
    "estimated_delivery": "2024-01-05",
    "current_location": "北京转运中心",
    "tracks": [
      {
        "time": "2024-01-03T10:00:00Z",
        "location": "北京转运中心",
        "description": "已发出"
      },
      {
        "time": "2024-01-02T18:00:00Z",
        "location": "上海仓库",
        "description": "已揽收"
      }
    ]
  }
}
```

### 4.2 催件

```
POST /api/v1/logistics/urge
```

**请求**：

```json
{
  "order_id": "ORD-001",
  "user_id": "user_123",
  "reason": "超过预计时间未收到"
}
```

### 4.3 拦截包裹

```
POST /api/v1/logistics/intercept
```

**请求**：

```json
{
  "order_id": "ORD-001",
  "reason": "用户取消订单"
}
```

---

## 5. 工单服务 (Ticket Service)

### 5.1 创建工单

```
POST /api/v1/tickets
```

**请求**：

```json
{
  "user_id": "user_123",
  "session_id": "sess_789",
  "category": "complaint",
  "priority": "high",
  "description": "收到的商品与描述不符",
  "attachments": ["https://..."],
  "metadata": {
    "order_id": "ORD-001",
    "product_id": "P001"
  }
}
```

**响应**：

```json
{
  "code": 0,
  "data": {
    "ticket_id": "TKT-001",
    "status": "open",
    "created_at": "2024-01-03T10:00:00Z",
    "estimated_response": "24小时内"
  }
}
```

### 5.2 查询工单

```
GET /api/v1/tickets/{ticket_id}
```

### 5.3 更新工单

```
PATCH /api/v1/tickets/{ticket_id}
```

**请求**：

```json
{
  "status": "in_progress",
  "assigned_to": "agent_001",
  "note": "已联系用户了解情况"
}
```

### 5.4 关闭工单

```
POST /api/v1/tickets/{ticket_id}/close
```

**请求**：

```json
{
  "resolution": "已为用户办理退款，预计3-5个工作日到账",
  "satisfaction": 4
}
```

---

## 6. 知识库服务 (Knowledge Service)

### 6.1 检索知识

```
POST /api/v1/knowledge/search
```

**请求**：

```json
{
  "query": "如何退货",
  "top_k": 5,
  "filters": {
    "category": "return_policy",
    "tenant_id": "tenant_001"
  }
}
```

**响应**：

```json
{
  "code": 0,
  "data": {
    "results": [
      {
        "id": "doc_001",
        "content": "退货流程：1. 在订单详情页申请退货...",
        "score": 0.92,
        "metadata": {
          "source": "help_center",
          "category": "return_policy",
          "updated_at": "2024-01-01"
        }
      }
    ]
  }
}
```

### 6.2 添加知识

```
POST /api/v1/knowledge/documents
```

**请求**：

```json
{
  "content": "退货政策更新：自2024年1月起...",
  "metadata": {
    "source": "policy_update",
    "category": "return_policy",
    "author": "admin"
  }
}
```

### 6.3 更新知识

```
PUT /api/v1/knowledge/documents/{doc_id}
```

### 6.4 删除知识

```
DELETE /api/v1/knowledge/documents/{doc_id}
```

---

## 7. Agent 对话接口

### 7.1 发送对话

```
POST /api/v1/chat/completions
```

**请求**：

```json
{
  "session_id": "sess_789",
  "user_id": "user_123",
  "message": "我要退货",
  "context": {
    "channel": "feishu",
    "user_info": {
      "nickname": "张三",
      "vip_level": "gold"
    }
  }
}
```

**响应**：

```json
{
  "code": 0,
  "data": {
    "session_id": "sess_789",
    "reply": "好的，请提供您的订单号，我帮您查询退货流程。",
    "intent": "return_goods",
    "confidence": 0.95,
    "tool_calls": [],
    "metadata": {
      "model": "claude-sonnet-4-6",
      "tokens_used": 150,
      "latency_ms": 800
    }
  }
}
```

### 7.2 流式对话

```
POST /api/v1/chat/stream
```

**响应** (SSE)：

```
data: {"type": "thinking", "content": "用户想要退货..."}
data: {"type": "tool_call", "tool": "query_order", "args": {"order_id": "ORD-001"}}
data: {"type": "tool_result", "tool": "query_order", "result": {...}}
data: {"type": "reply", "content": "好的，您的订单"}
data: {"type": "reply", "content": "ORD-001 目前状态是"}
data: {"type": "reply", "content": "已发货，可以申请退货。"}
data: {"type": "done", "metadata": {...}}
```

---

## 8. 错误码速查

| 错误码 | 说明 | HTTP Status |
|--------|------|-------------|
| 0 | 成功 | 200 |
| 10001 | 参数错误 | 400 |
| 10002 | 未授权 | 401 |
| 10003 | 无权限 | 403 |
| 10004 | 资源不存在 | 404 |
| 20001 | 订单不存在 | 404 |
| 20002 | 订单状态不允许操作 | 400 |
| 30001 | 快递单号无效 | 400 |
| 40001 | 工单创建失败 | 500 |
| 50001 | 知识库检索失败 | 500 |
| 90001 | 内部错误 | 500 |
| 90002 | 服务不可用 | 503 |
| 90003 | 请求超时 | 504 |
