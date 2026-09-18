# LiteLLM 网关部署手册

基于 LiteLLM Proxy 的统一 LLM 网关，提供多供应商接入、负载均衡、故障转移、限流、成本统计能力。

本文档包含：单点部署、配置说明、限流策略、集群部署、运维命令、数据备份与升级。

### 架构

```
直连模式（LITELLM_ENABLED=false，默认）:
  ChatOpenAI → DeepSeek API

网关模式（LITELLM_ENABLED=true）:
  ChatOpenAI (base_url=网关地址)
      └─ LiteLLM Proxy (Docker, port 4000)
            ├─ 模型路由 / 负载均衡 / 故障转移
            │     ├─ DeepSeek Key1 / Key2  （least-busy + 自动故障转移）
            │     ├─ Ollama 本地模型
            │     └─ （未来扩展其他供应商）
            ├─ Postgres — 密钥、成本统计、调用日志（持久化存储）
            └─ Redis    — 全局限流计数、缓存（多实例部署计数一致）
```

- **应用层透明**：开启网关只是换了 `base_url` 和 `api_key`，业务代码零改动
- **快速回滚**：`.env` 改一个开关立即回到直连模式，1 分钟内完成
- **生产就绪**：Postgres + Redis 架构，单点部署即可平滑升级为集群

### 单点部署（Docker Compose）

默认采用 **Postgres + Redis** 架构，而非 SQLite。好处：
- **数据可靠**：Postgres 持久化密钥、成本统计、调用日志，比 SQLite 更稳定
- **限流精确**：Redis 做全局限流计数，容器重启不丢失计数
- **平滑升级**：未来扩成集群直接加 litellm 实例 + Nginx 即可，存储层不用动

```
┌──────────────────────────────┐
│      LiteLLM Proxy           │
│    (网关 + Web UI, 4000)     │
└──────────┬───────────────────┘
           │
     ┌─────┴──────┐
     ▼            ▼
  Postgres      Redis
（密钥/成本/日志）（限流计数/缓存）
```

**部署步骤：**

```bash
cd litellm

# 1. 准备环境变量
cp litellm.env.example litellm.env
# 编辑 litellm.env，至少修改：
#   - LITELLM_MASTER_KEY（管理后台密钥）
#   - POSTGRES_PASSWORD（数据库密码）
#   - DEEPSEEK_API_KEY（DeepSeek API 密钥）

# 2. 启动（包含 postgres + redis + litellm 三个容器）
docker compose -f docker-compose.litellm.yaml up -d

# 3. 查看状态（三个服务都 healthy 才表示就绪）
docker compose -f docker-compose.litellm.yaml ps

# 4. 查看日志
docker compose -f docker-compose.litellm.yaml logs -f litellm
```

Web UI：`http://localhost:4000/ui`（使用 `litellm.env` 中的 `LITELLM_MASTER_KEY` 登录）

**常用运维命令：**

```bash
# 重启
docker compose -f docker-compose.litellm.yaml restart

# 停止（保留数据）
docker compose -f docker-compose.litellm.yaml stop

# 停止并删除容器（数据卷保留）
docker compose -f docker-compose.litellm.yaml down

# 完全清理（含数据，慎用！）
docker compose -f docker-compose.litellm.yaml down -v
docker volume rm litellm_postgres_data litellm_redis_data

# 升级镜像
docker compose -f docker-compose.litellm.yaml pull
docker compose -f docker-compose.litellm.yaml up -d
```

**数据备份：**

```bash
# Postgres 备份
docker exec litellm-postgres pg_dump -U litellm litellm > litellm_pg_backup_$(date +%Y%m%d).sql

# Redis 备份（RDB 文件）
docker exec litellm-redis redis-cli BGSAVE
docker cp litellm-redis:/data/dump.rdb ./redis_backup_$(date +%Y%m%d).rdb
```

---

### 集群部署（高可用，Nginx + 多实例）

当单实例扛不住流量，或需要网关层高可用时，升级到集群部署。

**架构：**

```
                     ┌── LiteLLM Proxy #1 ──┐
客户端 → Nginx →   ┤                     ├→ Postgres（共享）
    (4000)  负载均衡 └── LiteLLM Proxy #2 ──┘   Redis（共享）
```

**特点：**
- **高可用**：单实例挂了不影响整体服务
- **水平扩展**：加机器就能扛更多流量
- **全局限流**：Redis 做全局限流计数，多实例计数一致
- **共享状态**：API Key、成本数据、调用日志全部存在 Postgres

**部署步骤：**

```bash
# 假设两台服务器：192.168.1.10（Nginx + Postgres + Redis）
#              192.168.1.11、192.168.1.12（LiteLLM 实例）

# ===== 第一步：部署共享存储（Postgres + Redis）=====
# 在存储节点（192.168.1.10）上，只起 postgres 和 redis：

# 建议单独的 docker-compose.storage.yaml，内容参考单点版的 postgres + redis 部分
# 注意端口要对外开放（或在内网互通）

# ===== 第二步：部署多个 LiteLLM 实例 =====
# 在每个应用节点上，创建精简版 compose 文件（只有 litellm 服务）：

cat > docker-compose.app.yaml << 'EOF'
services:
  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    restart: unless-stopped
    ports:
      - "4000:4000"
    volumes:
      - ./litellm_config.yaml:/app/config.yaml:ro
    environment:
      DATABASE_URL: postgresql://litellm:password@192.168.1.10:5432/litellm
      REDIS_HOST: 192.168.1.10
      REDIS_PORT: 6379
      LITELLM_MASTER_KEY: sk-litellm-master-xxx
      # ... 其他环境变量
    command: --config /app/config.yaml --port 4000
    extra_hosts:
      - "host.docker.internal:host-gateway"
EOF

# 在每个应用节点启动
docker compose -f docker-compose.app.yaml up -d

# ===== 第三步：部署 Nginx 负载均衡 =====
# 在 192.168.1.10 上安装 Nginx，配置如下：

cat > /etc/nginx/conf.d/litellm.conf << 'EOF'
upstream litellm_backend {
    least_conn;                          # 最少连接负载均衡
    server 192.168.1.11:4000 max_fails=3 fail_timeout=30s;
    server 192.168.1.12:4000 max_fails=3 fail_timeout=30s;
    # 继续加实例...
    keepalive 32;                        # 长连接复用
}

server {
    listen 4000;
    server_name _;

    location / {
        proxy_pass http://litellm_backend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";       # 配合 keepalive
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # SSE 支持
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding on;

        # 超时设置（长连接/流式需要更长超时）
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
EOF

nginx -s reload
```

**注意事项：**
1. **配置文件同步**：所有 LiteLLM 实例的 `litellm_config.yaml` 必须一致。建议用 Git 管理，部署时同步下发。
2. **版本一致性**：所有实例使用相同版本的 LiteLLM 镜像，避免行为不一致。
3. **会话无关**：LiteLLM 本身是无状态的，请求不需要粘滞会话，Nginx 轮询/最少连接即可。
4. **SSE 长连接**：Nginx 必须关闭 proxy_buffering，否则流式响应会被缓存导致客户端收不到消息。
5. **滚动升级**：升级时逐个重启实例，保证总有实例可用。

---

### 从单点升级到集群

如果你先用单点部署，后面要扩成集群，步骤如下：

1. **数据层不变**：Postgres 和 Redis 已经是独立容器，直接复用
2. **新增实例**：在新机器上启动只含 litellm 服务的容器，指向同一个 Postgres + Redis
3. **加 Nginx**：在前面加 Nginx 做负载均衡，把新实例加进去
4. **切换流量**：逐步把流量从单点切到 Nginx

全程零停机，数据不迁移，非常平滑。

### 配置模型

所有模型配置在 `litellm/litellm_config.yaml` 中管理：

- **已启用**：DeepSeek V4 Flash、DeepSeek V4 Pro
- **注释模板**：第二个 DeepSeek Key（高可用）、Ollama 本地模型、Anthropic Claude、OpenAI GPT
- 新增模型：取消对应注释块，填入 API Key 即可，LiteLLM 自动热加载

### 限流策略

限流计数存储在 **Redis** 中，多实例部署时全局一致，不会因为有多个实例导致限流翻倍。

| 维度 | 配置位置 | 说明 |
|------|---------|------|
| 按模型 RPM/TPM | 每个 model 的 `litellm_params.rpm/tpm` | 单模型每分钟请求数 / token 数限制（Redis 全局计数） |
| 全局兜底限流 | `rate_limits` 段 | 所有模型加总的上限，防止整体超配额 |
| 按 API Key 并发 | `api_key_list[].max_parallel_requests` | 单虚拟 key 的最大并发请求数 |
| 应用层重试 | `infra/retry_utils.py` | 网关模式 1 次兜底，直连模式 3 次 |

触发限流时，网关返回 `429 Too Many Requests`，应用层捕获后走降级兜底（返回友好提示）。

### 两层重试架构

| 层级 | 位置 | 次数 | 作用 |
|------|------|------|------|
| 网关层（主） | LiteLLM `router_settings` | 3 次 | 跨 key/跨模型故障转移 + least-busy 负载均衡 |
| 应用层（备） | `with_llm_retry` | 1（网关）/ 3（直连） | 最后兜底 |
| 兜底层 | `with_fallback` | — | 返回友好提示 |

### 接入应用

在 `.env` 中设置：

```env
LITELLM_ENABLED=true
LITELLM_PROXY_URL=http://localhost:4000/v1
LITELLM_API_KEY=sk-my-app-proxy-key   # 对应 litellm_config.yaml 中 api_key_list 的 key
```

重启后端服务即可。前端模型列表会自动从网关动态获取。

### 与 Langfuse 的关系

- **LiteLLM**：网关层，负责多供应商路由、负载均衡、限流、**聚合级**成本统计
- **Langfuse**：可观测层，负责**调用级**链路追踪、Prompt/Response 记录、RAG 检索过程可视化
- 两者互补，互不替代

---
