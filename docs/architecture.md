# 智能客服 Agent 系统架构设计

## 1. 架构概览

### 1.1 设计原则

- **分层解耦**：接入层、编排层、业务层、数据层独立演进
- **降级兜底**：每一层都有 fallback 策略，确保服务不中断
- **可观测性**：全链路 trace，业务指标和技术指标双维度监控
- **安全第一**：用户数据脱敏，LLM 输出安全检查，Prompt 注入防护

### 1.2 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                       接入层 (Gateway)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │  飞书Bot  │  │ 微信客服  │  │  网页Chat │  │  APP SDK │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       └──────────────┴──────────────┴──────────────┘         │
│                           │                                  │
│                    ┌──────▼──────┐                           │
│                    │  Kafka 消息队列 │                        │
│                    └──────┬──────┘                           │
└───────────────────────────┼──────────────────────────────────┘
                            │
┌───────────────────────────┼──────────────────────────────────┐
│                    Agent 编排层 (Dify)                       │
│  ┌────────────────────────▼────────────────────────┐         │
│  │              意图识别 & 路由                      │         │
│  └───┬──────────────┬──────────────┬───────────────┘         │
│      │              │              │                          │
│  ┌───▼───┐    ┌─────▼─────┐  ┌────▼────┐                    │
│  │RAG检索 │    │ 工具调用   │  │人工转接 │                    │
│  │知识库  │    │ 订单/物流  │  │         │                    │
│  └───┬───┘    └─────┬─────┘  └────┬────┘                    │
│      │              │              │                          │
│  ┌───▼──────────────▼──────────────▼───┐                     │
│  │         回复生成 & 安全检查           │                     │
│  └─────────────────┬───────────────────┘                     │
└────────────────────┼─────────────────────────────────────────┘
                     │
┌────────────────────┼─────────────────────────────────────────┐
│                 业务服务层 (FastAPI)                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │订单服务   │ │物流服务   │ │工单服务   │ │知识库服务 │       │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘       │
│       └────────────┴────────────┴─────────────┘              │
└────────────────────┼─────────────────────────────────────────┘
                     │
┌────────────────────┼─────────────────────────────────────────┐
│                    数据层                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│  │PostgreSQL│ │  Milvus  │ │  Redis   │                     │
│  │业务数据   │ │向量知识库 │ │会话缓存   │                     │
│  └──────────┘ └──────────┘ └──────────┘                     │
└──────────────────────────────────────────────────────────────┘
```

## 2. 核心模块设计

### 2.1 接入层 (Gateway)

**职责**：统一消息接入，协议转换，流量控制

```python
# 核心接口
class MessageGateway:
    async def receive(self, channel: str, message: dict) -> None
    async def reply(self, session_id: str, response: dict) -> None
    async def transfer_to_human(self, session_id: str, context: dict) -> None
```

**多渠道适配**：
- 飞书：Event Subscription + Message API
- 微信：客服消息接口
- 网页：WebSocket 长连接
- APP：REST API + 推送

**流量控制**：
- 令牌桶限流（Redis 实现）
- 用户级频率限制：单用户 QPS ≤ 5
- 全局并发控制：最大同时对话数可配

### 2.2 Agent 编排层 (Dify)

**职责**：意图识别、任务路由、RAG 检索、工具调用、回复生成

#### 意图识别

```yaml
意图分类:
  - 订单查询: "查订单、订单状态、订单详情"
  - 物流查询: "快递到哪了、物流信息、什么时候到"
  - 退换货: "退货、换货、退款、申请售后"
  - 投诉: "投诉、不满意、差评、举报"
  - 咨询: "怎么买、优惠、活动、尺码"
  - 人工: "转人工、找客服、真人"
  - 闲聊: "其他非业务问题"
```

#### RAG 检索策略

```
用户 Query
    │
    ▼
┌───────────────┐
│  Query 改写    │  HyDE: 生成假设性答案
└───────┬───────┘
        │
    ┌───▼───┐
    │混合检索│  向量检索(70%) + BM25(30%)
    └───┬───┘
        │
    ┌───▼───┐
    │ Rerank │  Cross-encoder 重排序
    └───┬───┘
        │
    ┌───▼───┐
    │ Top-K  │  取 Top 5 作为上下文
    └───────┘
```

#### 工具调用

```python
# 工具定义 Schema
TOOLS = {
    "query_order": {
        "description": "查询订单详情，包括状态、金额、商品信息",
        "parameters": {
            "order_id": {"type": "string", "description": "订单号"},
            "user_id": {"type": "string", "description": "用户ID"}
        },
        "required": ["order_id"]
    },
    "track_logistics": {
        "description": "查询物流信息，包括当前位置、预计到达时间",
        "parameters": {
            "tracking_number": {"type": "string", "description": "快递单号"}
        },
        "required": ["tracking_number"]
    },
    "create_ticket": {
        "description": "创建客服工单，用于投诉、建议、复杂问题",
        "parameters": {
            "user_id": {"type": "string"},
            "category": {"type": "string", "enum": ["complaint", "suggestion", "technical", "other"]},
            "description": {"type": "string"},
            "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]}
        },
        "required": ["user_id", "category", "description"]
    }
}
```

### 2.3 业务服务层

#### 订单服务

```python
# 核心接口
class OrderService:
    async def query_order(self, order_id: str) -> OrderDetail
    async def cancel_order(self, order_id: str, reason: str) -> CancelResult
    async def modify_order(self, order_id: str, changes: dict) -> ModifyResult
    async def apply_refund(self, order_id: str, refund_info: dict) -> RefundResult
```

#### 物流服务

```python
class LogisticsService:
    async def track(self, tracking_number: str) -> LogisticsInfo
    async def urge_delivery(self, order_id: str) -> UrgeResult
    async def intercept_package(self, order_id: str) -> InterceptResult
```

#### 工单服务

```python
class TicketService:
    async def create_ticket(self, ticket_info: dict) -> Ticket
    async def update_ticket(self, ticket_id: str, update: dict) -> Ticket
    async def close_ticket(self, ticket_id: str, resolution: str) -> bool
    async def escalate_ticket(self, ticket_id: str, reason: str) -> bool
```

### 2.4 数据层

#### PostgreSQL Schema

```sql
-- 会话表
CREATE TABLE sessions (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    channel VARCHAR(32) NOT NULL,
    status VARCHAR(16) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 消息表
CREATE TABLE messages (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES sessions(id),
    role VARCHAR(16) NOT NULL,  -- user / assistant / system
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 工单表
CREATE TABLE tickets (
    id UUID PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    session_id UUID REFERENCES sessions(id),
    category VARCHAR(32) NOT NULL,
    priority VARCHAR(16) DEFAULT 'medium',
    status VARCHAR(16) DEFAULT 'open',
    description TEXT,
    resolution TEXT,
    assigned_to VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP
);
```

#### Milvus Collection

```python
# 知识库向量 Collection
collection_schema = {
    "name": "knowledge_base",
    "fields": [
        {"name": "id", "type": "VARCHAR", "max_length": 64},
        {"name": "content", "type": "VARCHAR", "max_length": 8192},
        {"name": "embedding", "type": "FLOAT_VECTOR", "dim": 1536},
        {"name": "metadata", "type": "JSON"},  # source, category, updated_at
        {"name": "tenant_id", "type": "VARCHAR", "max_length": 32}  # 多租户
    ]
}
```

## 3. 关键流程

### 3.1 标准问答流程

```
用户消息 → 意图识别 → RAG 检索 → Prompt 组装 → LLM 生成 → 安全检查 → 返回用户
```

### 3.2 工具调用流程

```
用户消息 → 意图识别 → 需要工具 → 参数提取 → 调用 API → 结果整合 → LLM 生成回复 → 返回用户
```

### 3.3 人工转接触发条件

- 用户主动要求转人工
- 连续 2 轮无法解决用户问题
- 检测到用户情绪激动（投诉、辱骂）
- 涉及敏感操作（大额退款、账户安全）
- Agent 置信度低于阈值

### 3.4 降级策略

```
正常流程
    │
    ├─ LLM 超时 → 降级到模板回复 + 转人工
    ├─ RAG 无结果 → 降级到通用话术 + 转人工
    ├─ API 调用失败 → 降级到知识库问答 + 记录待处理
    └─ 全部失败 → 直接转人工 + 告警
```

## 4. 安全设计

### 4.1 数据安全

- 用户手机号、地址等 PII 数据脱敏后传给 LLM
- 会话数据加密存储（AES-256）
- 日志中不记录用户敏感信息

### 4.2 LLM 安全

```python
# 输出安全检查
class OutputSafetyChecker:
    def check(self, response: str, context: dict) -> tuple[bool, str]:
        # 1. 检查是否包含内部信息泄露
        if self.contains_internal_info(response):
            return False, "contains_internal_info"
        # 2. 检查是否做出不可能的承诺
        if self.makes_impossible_promise(response):
            return False, "impossible_promise"
        # 3. 检查是否包含有害内容
        if self.contains_harmful_content(response):
            return False, "harmful_content"
        return True, "safe"
```

### 4.3 Prompt 注入防护

```python
# 输入过滤
class InputSanitizer:
    def sanitize(self, user_input: str) -> str:
        # 移除潜在的注入指令
        patterns = [
            r"ignore previous instructions",
            r"system prompt",
            r"your instructions are",
            # ... 更多模式
        ]
        for pattern in patterns:
            user_input = re.sub(pattern, "[filtered]", user_input, flags=re.IGNORECASE)
        return user_input
```

## 5. 性能指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 响应时间 P95 | < 3s | 从用户发送到收到回复 |
| 响应时间 P99 | < 5s | 极端情况 |
| 解决率 | > 70% | 无需转人工即可解决 |
| 人工转接率 | < 30% | 需要转人工的比例 |
| RAG 检索准确率 | > 85% | Top-5 命中率 |
| 工具调用成功率 | > 95% | API 调用成功 |
| 系统可用性 | 99.9% | 月度 SLA |
