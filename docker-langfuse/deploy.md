# Langfuse 可观测性平台部署手册

基于 Langfuse 开源 LLM 工程平台，实现全链路可观测性：追踪每次 LLM 调用的输入/输出、token 用量、延迟，可视化 RAG 检索和 Agent 工具调用过程。

本文档包含：平台搭建（Docker Compose 6 服务集群）、Python 项目集成、验证方法、运维命令、数据备份。

### 架构

```
HTTP 请求 → FastAPI 端点
              └─ _build_langchain_config() → langfuse_setup.py
                   ├─ CallbackHandler → RunnableConfig.callbacks
                   └─ metadata → langfuse_trace（name / session_id / user_id）
                        │
                        ▼
                   Langfuse SDK（异步上报）→ Langfuse 平台（Docker 自托管）
```

- **Agent 路径**：LangGraph 图级 callback 自动传播到所有节点（retrieve / agent / tools），单次请求对应一条完整 trace
- **RAG 路径**：retriever.invoke 与 chain.invoke 为两次独立 LCEL 调用，对应两条 trace（共享 session_id 可在 UI 中按会话聚合）

### 平台搭建（Docker Compose）

Langfuse 平台通过 Docker Compose 自托管，配置在 `docker-langfuse/` 目录下。

**服务组成**（6 个容器）：

| 服务 | 作用 | 端口 |
|------|------|------|
| langfuse-web | Web UI + API | 3000 |
| langfuse-worker | 后台任务（事件消费、导出等） | — |
| postgres | 主数据库 | 5432 |
| clickhouse | 分析型数据库（事件存储） | 8123 / 9000 |
| redis | 缓存 + 队列 | 6379 |
| minio | 对象存储（媒体文件、批量导出） | 9090 / 9091 |

**搭建步骤**：

```bash
cd docker-langfuse

# 1. 生成密钥并配置 .env（参考下文密钥清单）
# 2. 拉取镜像
docker compose pull

# 3. 后台启动
docker compose up -d

# 4. 等待所有服务 healthy（约 2-3 分钟）
docker compose ps

# 5. 查看日志
docker compose logs -f langfuse-web
```

启动成功后访问 `http://localhost:3000`，注册管理员账号并创建项目，在项目设置中获取 Public Key 和 Secret Key。

**密钥生成**（在 `.env` 中配置）：

```bash
# 生成随机密钥示例
openssl rand -hex 16   # SALT
openssl rand -hex 32   # POSTGRES_PASSWORD / ENCRYPTION_KEY / NEXTAUTH_SECRET / CLICKHOUSE_PASSWORD 等
```

需要配置的密钥清单：
- `POSTGRES_PASSWORD` / `DATABASE_URL`（密码需一致）
- `SALT`、`ENCRYPTION_KEY`、`NEXTAUTH_SECRET`
- `CLICKHOUSE_PASSWORD`
- `REDIS_AUTH`
- `MINIO_ROOT_PASSWORD`（3 个 S3 SECRET_ACCESS_KEY 与其一致）

> **国内镜像加速**：如直接拉取镜像超时，在 Docker Desktop 配置镜像加速器，并将 `docker-compose.yml` 中的镜像地址从 `docker.langfuse.com/langfuse/...` 改为 `langfuse/...`（走 Docker Hub）。

### Python 项目集成

**1. 安装依赖**

```bash
pip install langfuse
```

> 国内可用阿里云镜像：`pip install langfuse -i https://mirrors.aliyun.com/pypi/simple/`

**2. 配置环境变量**

在项目 `.env` 中添加（来自 Langfuse 项目设置页面）：

```env
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LANGFUSE_HOST=http://localhost:3000
```

**3. 验证**

启动后端服务后，在前端发送一条消息，然后打开 Langfuse Web UI（`http://localhost:3000`），在 Traces 页面应能看到对应的追踪记录：
- 普通聊天：VectorStoreRetriever + RunnableSequence 两条 trace
- Agent 聊天：单条 trace，包含 retrieve / agent / tools 等多个 span

**降级策略**：未配置 `LANGFUSE_*` 环境变量或 SDK 不可用时，`langfuse_setup.py` 自动返回 None，所有接口正常工作，无任何报错。

