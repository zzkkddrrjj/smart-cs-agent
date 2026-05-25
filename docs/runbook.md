# 运维手册

## 1. 部署指南

### 1.1 环境要求

| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 4核 | 8核 |
| 内存 | 16GB | 32GB |
| 磁盘 | 100GB SSD | 500GB SSD |
| 操作系统 | Ubuntu 22.04 / CentOS 8 | Ubuntu 22.04 |
| Docker | 24.0+ | 24.0+ |
| Docker Compose | 2.20+ | 2.20+ |

### 1.2 快速启动

```bash
# 1. 克隆项目
git clone <repo-url> smart-cs-agent
cd smart-cs-agent

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置密钥和数据库密码

# 3. 启动所有服务
docker-compose up -d

# 4. 检查服务状态
docker-compose ps

# 5. 查看日志
docker-compose logs -f
```

### 1.3 环境变量配置

```bash
# .env 文件配置

# 数据库
POSTGRES_USER=smartcs
POSTGRES_PASSWORD=<strong-password>
POSTGRES_DB=smartcs

# Redis
REDIS_PASSWORD=<strong-password>

# MinIO (Milvus 存储)
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=<strong-password>

# Dify
SECRET_KEY=<random-secret-key>

# LLM API
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx

# 服务配置
LOG_LEVEL=INFO
```

### 1.4 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| Nginx | 80/443 | 主入口 |
| Dify Web | 3000 | 管理界面 |
| Dify API | 5001 | API 服务 |
| 订单服务 | 8001 | 订单查询/取消 |
| 物流服务 | 8002 | 物流查询/催件 |
| 工单服务 | 8003 | 工单管理 |
| 知识库服务 | 8004 | 知识检索 |
| PostgreSQL | 5432 | 数据库 |
| Redis | 6379 | 缓存 |
| Milvus | 19530 | 向量数据库 |
| Kafka | 9092 | 消息队列 |

---

## 2. 监控配置

### 2.1 Prometheus 配置

```yaml
# deploy/monitoring/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'order-service'
    static_configs:
      - targets: ['order-service:8001']
    metrics_path: '/metrics'

  - job_name: 'logistics-service'
    static_configs:
      - targets: ['logistics-service:8002']
    metrics_path: '/metrics'

  - job_name: 'ticket-service'
    static_configs:
      - targets: ['ticket-service:8003']
    metrics_path: '/metrics'

  - job_name: 'knowledge-service'
    static_configs:
      - targets: ['knowledge-service:8004']
    metrics_path: '/metrics'

  - job_name: 'dify-api'
    static_configs:
      - targets: ['dify-api:5001']
    metrics_path: '/metrics'

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  - job_name: 'milvus'
    static_configs:
      - targets: ['milvus:9091']
    metrics_path: '/metrics'
```

### 2.2 Grafana Dashboard

核心监控指标：

**业务指标**
- 对话量：每小时/每天的对话数
- 解决率：无需转人工的对话比例
- 人工转接率：需要转人工的比例
- 平均响应时间：从用户提问到收到回复
- 用户满意度：基于用户反馈评分

**技术指标**
- LLM 延迟：API 调用响应时间
- RAG 检索命中率：Top-K 命中比例
- 工具调用成功率：API 调用成功比例
- 错误率：5xx 错误比例
- 系统资源：CPU、内存、磁盘使用率

### 2.3 告警规则

```yaml
# deploy/monitoring/alerts.yml
groups:
  - name: business_alerts
    rules:
      - alert: HighTransferRate
        expr: transfer_rate > 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "人工转接率过高"
          description: "当前转接率为 {{ $value }}%，超过50%阈值"

      - alert: LowResolutionRate
        expr: resolution_rate < 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "解决率过低"
          description: "当前解决率为 {{ $value }}%，低于50%阈值"

      - alert: HighResponseTime
        expr: response_time_p99 > 5
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "响应时间过长"
          description: "P99响应时间为 {{ $value }}s，超过5s阈值"

  - name: service_alerts
    rules:
      - alert: ServiceDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "服务宕机"
          description: "{{ $labels.instance }} 服务不可用"

      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "错误率过高"
          description: "5xx错误率为 {{ $value }}%，超过10%阈值"

      - alert: HighCPUUsage
        expr: process_cpu_usage > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "CPU使用率过高"
          description: "CPU使用率为 {{ $value }}%，超过80%阈值"

      - alert: HighMemoryUsage
        expr: process_memory_usage > 0.85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "内存使用率过高"
          description: "内存使用率为 {{ $value }}%，超过85%阈值"
```

### 2.4 告警通知

```yaml
# 飞书告警配置
receivers:
  - name: feishu
    webhook_configs:
      - url: 'https://open.feishu.cn/open-apis/bot/v2/hook/<webhook-id>'
        send_resolved: true
        title: '{{ .CommonAnnotations.summary }}'
        text: |
          告警名称: {{ .CommonLabels.alertname }}
          告警级别: {{ .CommonLabels.severity }}
          告警详情: {{ .CommonAnnotations.description }}
          触发时间: {{ .StartsAt }}
          当前状态: {{ .Status }}
```

---

## 3. 故障排查

### 3.1 常见问题

#### 服务无法启动

```bash
# 检查容器状态
docker-compose ps

# 查看服务日志
docker-compose logs <service-name>

# 检查端口占用
netstat -tulpn | grep <port>

# 检查资源使用
docker stats
```

#### 数据库连接失败

```bash
# 检查 PostgreSQL 状态
docker-compose exec postgres pg_isready

# 检查数据库日志
docker-compose logs postgres

# 测试连接
docker-compose exec postgres psql -U smartcs -d smartcs
```

#### Milvus 连接失败

```bash
# 检查 Milvus 状态
docker-compose exec milvus curl http://localhost:9091/healthz

# 检查依赖服务
docker-compose ps etcd minio

# 查看 Milvus 日志
docker-compose logs milvus
```

#### LLM API 调用失败

```bash
# 检查 API Key 配置
echo $OPENAI_API_KEY

# 测试 API 连通性
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# 检查网络代理
echo $HTTP_PROXY
echo $HTTPS_PROXY
```

### 3.2 性能问题

#### 响应时间长

1. **检查 LLM 延迟**
   - 查看 Grafana 中的 LLM 响应时间
   - 考虑切换更快的模型（如 GPT-4o-mini）

2. **检查 RAG 检索**
   - 查看 Milvus 查询延迟
   - 优化索引参数（nlist、nprobe）

3. **检查工具调用**
   - 查看外部 API 响应时间
   - 增加超时和重试配置

#### 内存占用高

```bash
# 查看容器内存使用
docker stats --no-stream

# 检查 Milvus 内存
docker-compose exec milvus cat /proc/meminfo

# 调整 Milvus 缓存大小
# 在 docker-compose.yml 中添加环境变量：
# MILVUS_CACHE_SIZE: 4GB
```

### 3.3 数据问题

#### 知识库检索不准确

1. **检查向量质量**
   ```bash
   # 查看集合统计
   docker-compose exec milvus curl http://localhost:9091/collections
   ```

2. **重新索引**
   ```bash
   # 运行重新索引脚本
   python scripts/eval/reindex.py
   ```

3. **调整检索参数**
   - 增加 top_k 值
   - 调整相似度阈值
   - 尝试混合检索（向量 + BM25）

#### 工单数据丢失

```bash
# 检查 PostgreSQL 数据
docker-compose exec postgres psql -U smartcs -d smartcs -c "SELECT COUNT(*) FROM tickets;"

# 检查备份状态
ls -la /backup/postgres/

# 恢复备份
docker-compose exec postgres pg_restore -U smartcs -d smartcs /backup/latest.dump
```

---

## 4. 扩缩容指南

### 4.1 水平扩展

#### 扩展业务服务

```bash
# 扩展订单服务到 3 个实例
docker-compose up -d --scale order-service=3

# 扩展物流服务
docker-compose up -d --scale logistics-service=2

# 扩展工单服务
docker-compose up -d --scale ticket-service=2
```

#### 扩展 Dify Worker

```bash
# 扩展 Dify Worker 处理能力
docker-compose up -d --scale dify-worker=3
```

### 4.2 垂直扩展

#### 调整资源限制

```yaml
# docker-compose.yml 中添加资源限制
services:
  order-service:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

### 4.3 Kubernetes 部署

```yaml
# deploy/k8s/order-service-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: order-service
  template:
    metadata:
      labels:
        app: order-service
    spec:
      containers:
      - name: order-service
        image: smart-cs/order-service:latest
        ports:
        - containerPort: 8001
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: order-service
spec:
  selector:
    app: order-service
  ports:
  - port: 8001
    targetPort: 8001
  type: ClusterIP
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: order-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

---

## 5. 备份恢复

### 5.1 PostgreSQL 备份

```bash
# 全量备份
docker-compose exec postgres pg_dump -U smartcs -d smartcs > backup_$(date +%Y%m%d).sql

# 自动备份脚本
#!/bin/bash
BACKUP_DIR="/backup/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
docker-compose exec -T postgres pg_dump -U smartcs -d smartcs | gzip > "$BACKUP_DIR/backup_$DATE.sql.gz"

# 保留最近 7 天备份
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
```

### 5.2 Milvus 备份

```bash
# 创建快照
docker-compose exec milvus milvus-backup create -c knowledge_base

# 恢复快照
docker-compose exec milvus milvus-backup restore -c knowledge_base
```

### 5.3 Redis 备份

```bash
# 触发 RDB 快照
docker-compose exec redis redis-cli -a $REDIS_PASSWORD BGSAVE

# 复制备份文件
docker cp smart-cs-redis:/data/dump.rdb ./backup/redis_$(date +%Y%m%d).rdb
```

---

## 6. 日常运维

### 6.1 日志管理

```bash
# 查看实时日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f order-service

# 日志轮转配置（在 docker-compose.yml 中添加）
services:
  order-service:
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"
```

### 6.2 清理维护

```bash
# 清理未使用的 Docker 资源
docker system prune -a

# 清理未使用的卷
docker volume prune

# 清理未使用的网络
docker network prune
```

### 6.3 健康检查

```bash
# 检查所有服务健康状态
for service in order-service logistics-service ticket-service knowledge-service; do
  echo "Checking $service..."
  curl -s http://localhost:$(port)/health | jq .
done

# 检查数据库连接
docker-compose exec postgres pg_isready

# 检查 Redis 连接
docker-compose exec redis redis-cli -a $REDIS_PASSWORD ping

# 检查 Milvus 连接
docker-compose exec milvus curl http://localhost:9091/healthz
```

---

## 7. 回滚流程

### 7.1 代码回滚

```bash
# 查看部署历史
git log --oneline -10

# 回滚到指定版本
git checkout <commit-hash>
docker-compose up -d --build

# 或使用镜像标签
docker-compose down
# 修改 docker-compose.yml 中的镜像标签
docker-compose up -d
```

### 7.2 数据库回滚

```bash
# 停止服务
docker-compose down

# 恢复数据库备份
docker-compose up -d postgres
docker-compose exec -T postgres psql -U smartcs -d smartcs < backup_20240101.sql

# 启动服务
docker-compose up -d
```

---

## 8. 安全运维

### 8.1 密钥轮换

```bash
# 生成新密钥
openssl rand -hex 32

# 更新 .env 文件
vi .env

# 重启服务
docker-compose restart
```

### 8.2 安全扫描

```bash
# 扫描镜像漏洞
docker scan smart-cs/order-service:latest

# 检查依赖漏洞
pip-audit
```

### 8.3 访问审计

```bash
# 查看 Nginx 访问日志
tail -f /var/log/nginx/access.log

# 分析异常请求
grep "403\|401\|500" /var/log/nginx/access.log
```
