# 智能客服 Agent 项目规范

## 项目概述

电商全场景智能客服 Agent，基于 Dify + LangChain 架构，覆盖售后咨询、工单处理等核心场景。

## 技术栈

- **Agent 编排**: Dify（可视化工作流、RAG、工具调用）
- **后端服务**: Python 3.11+ / FastAPI
- **LLM**: Claude API / GPT-4o（按场景分层调用）
- **向量数据库**: Milvus
- **关系数据库**: PostgreSQL
- **缓存**: Redis
- **消息队列**: Kafka
- **部署**: Docker Compose → K8s

## 目录结构

```
smart-cs-agent/
├── docs/                    # 文档（架构、API 规范、运维手册）
├── services/                # 后端微服务
│   ├── gateway/             # 消息接入网关
│   ├── order-service/       # 订单服务
│   ├── logistics-service/   # 物流服务
│   ├── ticket-service/      # 工单服务
│   └── knowledge-service/   # 知识库管理
├── dify/                    # Dify 配置
│   ├── workflows/           # 工作流 YAML
│   ├── prompts/             # Prompt 模板
│   └── tools/               # 工具 Schema
├── rag/                     # RAG 管道
│   ├── ingestion/           # 文档摄入
│   ├── retrieval/           # 检索策略
│   └── evaluation/          # 评测脚本
├── tests/                   # 测试
├── deploy/                  # 部署配置
└── scripts/                 # 工具脚本
```

## 开发规范

### 代码风格
- Python: PEP 8，type hints 必须，docstring 简洁
- 命名：snake_case（变量/函数）、PascalCase（类）、UPPER_CASE（常量）
- import 顺序：标准库 → 三方库 → 本地模块，空行分隔

### Git 规范
- 分支：main（生产）、develop（开发）、feature/*、fix/*
- Commit: `<type>(<scope>): <description>`，英文描述
- type: feat / fix / docs / refactor / test / chore
- 不要自动 git push，等我说

### API 规范
- RESTful，JSON 请求/响应
- 统一响应格式：`{"code": int, "message": str, "data": any}`
- 错误码分层：业务错误码 5 位，前 2 位标识服务
- 所有接口必须有入参校验和出参类型定义

### Prompt 规范
- System Prompt 分层：基础人设 → 业务规则 → 场景特化
- 模板使用 Jinja2 语法
- 所有 Prompt 变更需记录到 dify/prompts/ 并标注版本

### 测试规范
- 单元测试覆盖率 > 80%
- Golden Test Set：标准问答对，每次 Prompt/RAG 变更后回归
- 集成测试：完整对话链路端到端验证

## 安全红线

- 密钥、token 不进代码、不进 commit
- LLM 输出必须经过安全检查才能返回用户
- 用户数据脱敏后才能传给 LLM
- Prompt 注入防护：输入过滤 + 输出检查
- 所有外部 API 调用必须有超时和熔断

## 部署流程

1. 本地 Docker Compose 验证
2. 测试环境自动部署（CI/CD）
3. 生产环境灰度发布（10% → 30% → 100%）
4. 回滚方案：保留前 3 个版本镜像

## 运维要点

- 监控：Prometheus + Grafana，业务指标 + 技术指标双维度
- 告警：解决率突降、错误率飙升、响应超时 → 飞书通知
- 日志：结构化 JSON 日志，含 trace_id 串联全链路
- 备份：PostgreSQL 每日全量 + WAL 增量，Milvus 快照
