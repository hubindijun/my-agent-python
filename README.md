# My RAG & Agent Service

基于 **LangChain + LangGraph + LiteLLM 网关 + 本地 Embedding + ChromaDB + FastAPI + Vue3** 构建的企业级智能对话服务。内置 **RAG 检索增强生成** 与 **LangGraph Agent（ReAct 工具调用）** 两套对话体系，配套 **LiteLLM 统一网关（多供应商/负载均衡/限流/成本统计）**、**Langfuse 全链路可观测性** 与 **MCP 协议工具桥接**能力，可快速对接外部业务系统（如 Spring Boot）。

## 核心特性

### 🔍 RAG 检索增强生成
- 本地 Embedding 模型（BAAI/bge-small-zh-v1.5）生成中文文本向量
- ChromaDB 持久化向量存储，相似度阈值检索（score_threshold=0.3）过滤低相关文档
- 独立的 `/chat*` 接口体系，流式输出（SSE）逐字渲染

### 🤖 LangGraph Agent 智能体
- 基于 LangGraph StateGraph 构建，图结构：`retrieve → agent ↔ tools → END`
- ReAct 模式工具调用循环，内置 RAG 检索节点 + 工具错误自动重试（最多 2 次）
- 支持**本地工具**（calculator 等）与 **MCP 外部工具**（Spring Boot 等）双层工具体系
- 独立的 `/agent/chat*` 接口体系，与普通 RAG 完全隔离

### 🔌 MCP 工具桥接（Spring Boot 集成）
- 通过 MCP (Model Context Protocol) over SSE 桥接外部业务系统
- 将 Spring Boot 等后端服务的业务能力（数据库、缓存、业务接口）以工具形式暴露给 Agent
- 优雅降级：服务不可用时自动跳过，Agent 正常运行仅使用本地工具
- 多服务支持、API Key 认证、超时可配置，零侵入 Agent 核心代码

### 🌐 LiteLLM 统一网关
- **多模型 / 多供应商统一接入**：DeepSeek、OpenAI、Anthropic、Ollama 本地模型等，一个接口调用所有供应商
- **负载均衡与故障转移**：多 API Key 轮询/最少并发策略，自动故障转移，单 key 失败无感切换
- **双层限流**：按模型（RPM/TPM）+ 按 API Key（并发数），保护配额防止超支
- **成本统计**：Web UI 实时查看 token 用量和费用，支持按模型/按 key 维度统计
- **环境变量开关**：`LITELLM_ENABLED` 控制，默认关闭（直连模式），开启后自动切到网关
- 与现有 Langfuse 监控互补：网关做聚合统计，Langfuse 做链路追踪

### 📊 Langfuse 全链路可观测
- Docker Compose 自托管 6 服务集群（Web + Worker + Postgres + ClickHouse + Redis + MinIO）
- 追踪每次 LLM 调用的输入/输出、Token 用量、延迟
- 可视化 RAG 检索过程与 Agent 工具调用链路
- 优雅降级：未配置或 SDK 不可用时自动跳过，不影响主流程

### 💬 前端 & 交互
- Vue3 + Arco Design + Tailwind，微信风格聊天界面
- 双页面路由：`/` RAG 问答 / `/agent` Agent 对话，顶部滑动切换
- 多模型动态切换（deepseek-v4-flash / deepseek-v4-pro），会话级绑定
- 流式逐字渲染 + 光标闪烁，会话历史存储于 sessionStorage

### 🛡️ 可靠性保障
- 分层异常体系（RAGBaseException 根类，10+ 子类细分错误类型）
- LLM 调用指数退避重试（3 次，可重试错误：限流/超时/服务端/连接）
- 兜底降级机制：LLM 不可用时返回友好提示，服务不中断
- 本地 Embedding 离线加载，启动不依赖外部网络

---

## 目录

- [核心特性](#核心特性)
- [项目结构](#项目结构)
- [技术栈](#技术栈)
- [环境要求](#环境要求)
- [安装部署](#安装部署)
- [快速开始](#快速开始)
- [API 文档](#api-文档)
- [前端说明](#前端说明)
- [核心模块说明](#核心模块说明)
- [项目调用链路](#项目调用链路)
- [LiteLLM 网关](#litellm-网关)
- [Langfuse 监控](#langfuse-监控)

---

## 项目结构

```
my/
├── app_server.py              # FastAPI 服务入口（普通聊天 + Agent 接口）
├── pre_load_rag_index.py      # 向量数据库初始化脚本
├── main.py                    # 命令行测试入口
│
├── core/                      # 核心领域层
│   ├── config.py              # 集中配置管理（所有环境变量统一入口）
│   ├── llm_client.py          # 统一 LLM 客户端（MyChat + MyAgent 共享）
│   ├── my_rag.py              # RAG 核心服务（ChromaDB 检索）
│   ├── my_chat.py             # LLM 聊天封装（带重试 + 兜底）
│   ├── my_agent.py            # LangGraph Agent（RAG 节点 + ReAct 工具循环）
│   └── rag_utils.py           # 混合重排工具（HybridReranker）
│
├── tools/                     # Agent 工具层
│   ├── agent_tools.py         # 本地工具工厂函数（calculator 等）
│   └── mcp_client.py          # MCP 客户端封装（桥接外部 MCP 服务工具）
│
├── infra/                     # 基础设施层
│   ├── exceptions.py          # 分层异常体系
│   ├── retry_utils.py         # LLM 调用重试 + 兜底装饰器
│   └── langfuse_setup.py      # Langfuse 监控集成（CallbackHandler 工厂 + 降级兜底）
│
├── scripts/                   # 启动脚本
│   ├── start-backend.sh       # 后端一键启动（自动激活 conda 环境）
│   └── start-frontend.sh      # 前端一键启动（自动检查依赖）
│
├── docker-litellm/             # LiteLLM 网关（Docker 部署）
│   ├── docker-compose.yml     # 容器编排（postgres + redis + litellm）
│   ├── litellm_config.yaml    # 模型/限流/负载均衡配置
│   ├── litellm.env.example    # 环境变量模板
│   └── deploy.md              # 部署手册（单点 + 集群）
│
├── chroma_db/                 # Chroma 向量数据库文件（运行后生成）
├── embeddings/                # 本地 Embedding 模型缓存（运行后自动下载）
│
├── chat-web/                  # Vue3 前端
│   ├── src/
│   │   ├── App.vue            # 顶部布局 + 路由出口 + 动态模型列表
│   │   ├── views/             # 页面组件（ChatRAG.vue / ChatAgent.vue）
│   │   ├── router/index.js    # vue-router 配置
│   │   ├── main.js
│   │   └── style.css
│   ├── index.html
│   ├── vite.config.js         # Vite 配置 + 代理
│   ├── tailwind.config.js
│   └── package.json
│
├── .env                       # 环境变量配置
├── requirements.txt           # Python 依赖清单
├── README.md                  # 项目说明文档
└── README_EN.md               # English documentation

├── docker-langfuse/           # Langfuse 监控平台 Docker Compose 配置
│   ├── docker-compose.yml     # 6 服务编排（web + worker + Postgres + ClickHouse + Redis + MinIO）
│   └── .env                   # Langfuse 平台密钥配置（不提交到 git）
```

---

## 技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| LLM 框架 | LangChain | 编排 RAG 流程、Prompt 管理 |
| Agent 框架 | LangGraph | 状态图编排，支持 ReAct 工具循环 + 记忆 |
| 嵌入模型 | BAAI/bge-small-zh-v1.5 | 中文 Embedding 模型，本地运行 |
| 向量数据库 | ChromaDB | 轻量级本地向量存储 |
| 大语言模型 | DeepSeek V4 (Flash / Pro) | 支持前端动态切换，OpenAI 兼容接口 |
| LLM 网关 | LiteLLM Proxy | 多供应商统一接入、负载均衡、故障转移、限流、成本统计 |
| 可观测性 | Langfuse | LLM 调用追踪、RAG 链路监控、Agent 工具执行可视化 |
| MCP 协议 | langchain-mcp-adapters + mcp SDK | 桥接外部 MCP 服务（如 Spring Boot）的工具到 Agent |
| Web 框架 | FastAPI | 高性能异步 HTTP 服务 |
| 前端框架 | Vue 3 + Vite + vue-router | 聊天界面，双页面路由 |
| UI 组件库 | Arco Design Vue | 基础组件 |
| 样式方案 | Tailwind CSS | 原子化 CSS |
| 环境管理 | Conda + pip | mylearn 虚拟环境（Python 3.11） |

---

## 环境要求

- Python >= 3.11
- Node.js >= 20 LTS（Node 24 不兼容 esbuild）
- Conda（推荐使用 miniconda 或 anaconda）
- 至少 2GB 可用磁盘空间（用于 Embedding 模型和向量库）

---

## 安装部署

### 1. 创建并激活 Conda 环境

```bash
conda create -n mylearn python=3.11 -y
conda activate mylearn
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

> 国内下载慢可使用清华源：`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

### 3. 配置环境变量

编辑 `.env` 文件：

```env
# ===== LLM 配置（默认 DeepSeek，可替换为任意 OpenAI 兼容接口）=====
OPENAI_API_KEY=你的_api_key
OPENAI_MODEL=deepseek-chat
OPENAI_API_BASE=https://api.deepseek.com/v1

# 直连模式模型白名单（逗号分隔）
ALLOWED_MODELS=deepseek-v4-flash,deepseek-v4-pro

# ===== Embedding 模型离线加载 =====
# 避免启动时访问 HuggingFace
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1

# ===== LiteLLM 网关（可选，默认关闭，开启后走统一网关）=====
LITELLM_ENABLED=false
LITELLM_PROXY_URL=http://localhost:4000/v1
LITELLM_API_KEY=sk-my-app-proxy-key
# 应用层重试次数（留空=自动：网关模式 1 次，直连模式 3 次）
LLM_RETRY_ATTEMPTS=

# ===== Langfuse 可观测性平台（可选，不配置则不启用监控）=====
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LANGFUSE_HOST=http://localhost:3000

# ===== MCP 服务配置（可选，桥接外部 MCP 服务的工具到 Agent）=====
MCP_ENABLED=true
MCP_SPRINGBOOT_URL=http://localhost:8080/mcp/sse
MCP_SPRINGBOOT_TIMEOUT=10
MCP_SPRINGBOOT_API_KEY=
```

### 4. 安装前端依赖

```bash
cd chat-web
npm install
```

---

## 快速开始

### 第一步：初始化向量数据库

首次运行需要创建知识库并生成向量索引：

```bash
python pre_load_rag_index.py
```

执行成功后会生成 `chroma_db/` 文件夹。

> 如需重建：`rm -rf chroma_db && python pre_load_rag_index.py`

### 第二步：启动后端服务

**方式一：一键启动脚本（推荐）**

```bash
./scripts/start-backend.sh
```

自动检测并激活 conda 环境（mylearn），以自动重载模式启动 uvicorn。

**方式二：手动启动**

```bash
uvicorn app_server:app --host 0.0.0.0 --port 8000 --reload
```

### 第三步：启动前端

**方式一：一键启动脚本（推荐）**

新开一个终端窗口：

```bash
./scripts/start-frontend.sh
```

自动检查 Node 环境和依赖，首次启动自动安装 npm 包。

**方式二：手动启动**

```bash
cd chat-web
npm run dev
```

浏览器打开 `http://localhost:5173` 即可开始对话。

---

## API 文档

启动后端后，访问 `http://localhost:8000/docs` 查看 Swagger UI。

### `GET /`

健康检查。

### `POST /chat`

一次性 RAG 问答。

**请求体：**

```json
{
  "query": "你的问题",
  "model": "deepseek-v4-flash"
}
```

- `query`（必填）：用户问题
- `model`（可选）：模型名称，可选 `deepseek-v4-flash` / `deepseek-v4-pro`，不传则使用会话当前模型或默认值

**响应：** `{ "query": "...", "answer": "...", "session_id": "...", "model": "...", "is_fallback?": true }`

### `POST /chat/stream`

流式对话（SSE）。支持多轮记忆，支持动态选择模型。

**请求头：** `X-Session-Id`（可选，用于续接会话；不传则新建）

**请求体：**

```json
{
  "query": "你的问题",
  "model": "deepseek-v4-flash"
}
```

- `query`（必填）：用户问题
- `model`（可选）：模型名称，可选 `deepseek-v4-flash` / `deepseek-v4-pro`，不传则使用会话当前模型或默认值

**响应：** `text/event-stream`，JSON 结构化事件（`data: {...}\n\n` 格式）：

| 类型 | 字段 | 说明 |
|------|------|------|
| `session` | `session_id`, `model` | 第一条消息，返回会话 ID 和当前模型 |
| `text` | `content` | 文本片段（多次） |
| `fallback` | `message` | LLM 调用失败，已返回兜底回复 |
| `error` | `code`, `message` | 不可恢复错误 |
| `done` | — | 流式结束 |

### `GET /chat/history`

获取当前会话历史记录。需要 `X-Session-Id` 请求头。

### `DELETE /chat/history`

清空当前会话历史记录。需要 `X-Session-Id` 请求头。

---

### `POST /agent/chat`

Agent 非流式对话。基于 LangGraph，内置 RAG 检索节点 + ReAct 工具循环。

**请求头：** `X-Session-Id`（可选）

**请求体：**

```json
{
  "query": "你的问题",
  "model": "deepseek-v4-flash"
}
```

**响应：** `{ "query": "...", "answer": "...", "session_id": "...", "model": "...", "tool_calls?": [...], "is_fallback?": true }`

### `POST /agent/chat/stream`

Agent 流式对话（SSE）。事件格式与 `/chat/stream` 对齐，额外支持 `tool_call` / `tool_result` 事件（前端可忽略）。

**事件类型：**

| 类型 | 字段 | 说明 |
|------|------|------|
| `session` | `session_id`, `model` | 第一条消息 |
| `text` | `content` | 文本片段（多次） |
| `tool_call` | `name`, `args` | Agent 调用工具（新增） |
| `tool_result` | `name`, `content` | 工具执行结果（新增） |
| `fallback` | `message` | LLM 失败，已兜底 |
| `error` | `code`, `message` | 不可恢复错误 |
| `done` | — | 流式结束 |

### `GET /agent/chat/history`

获取 Agent 会话历史（含工具消息）。需要 `X-Session-Id`。

### `DELETE /agent/chat/history`

清空 Agent 会话历史。需要 `X-Session-Id`。

---

## 前端说明

### 功能特性

- 🎨 微信风格聊天界面
- 🤖 模型切换 — 顶部下拉可选 DeepSeek V4 Flash / Pro，会话级绑定
- ⚡ 流式输出，逐字渲染 + 光标闪烁效果
- 💾 会话历史保存在 `sessionStorage`（刷新保留，关闭浏览器丢失）
- 🏷️ 快捷问题标签，点击即问
- 🗑️ 一键清空聊天记录（含二次确认）
- ⌨️ Enter 发送 / Shift+Enter 换行

### 会话机制

- 前端通过 `X-Session-Id` header 与后端会话绑定
- `session_id`、消息记录、**当前选择的模型**都存储在 `sessionStorage` 中
- 后端会话存储在内存中，结构为 `{ history: [...], model: "deepseek-v4-flash" }`，重启后端服务会丢失所有会话
- 每个会话最多保留 20 条消息（10 轮对话）
- 模型选择与会话绑定，切换后当前会话后续消息使用新模型

---

## 核心模块说明

### 入口文件

#### app_server.py

FastAPI HTTP 服务入口。接收 HTTP 请求，调用 MyRag 服务处理业务逻辑，返回 JSON 或 SSE 流式结果。

- 使用内存字典维护多会话，结构：`{ session_id: { history: [...], model: "deepseek-v4-flash" } }`
- 支持请求体传 `model` 参数动态切换模型（可选 `deepseek-v4-flash` / `deepseek-v4-pro`）
- 三层全局异常处理器：RAGBaseException / 校验异常 / 兜底异常
- SSE 事件为 JSON 结构化格式（`session` / `text` / `fallback` / `error` / `done`）

#### pre_load_rag_index.py

向量数据库初始化脚本。使用 `RecursiveCharacterTextSplitter`（中文分隔符，chunk_size=200，overlap=20）分割文档并写入 ChromaDB。

#### main.py

CLI 快速测试入口，验证 RAG 链路是否正常。

### core/ — 核心领域层

#### core/config.py

集中配置管理模块。统一从 `.env` 读取所有环境变量，替代散落的 `os.getenv()`。

- `get_settings()` — 获取全局单例 Settings
- `effective_base_url` / `effective_api_key` — 根据 `LITELLM_ENABLED` 自动切换直连/网关地址
- `effective_retry_attempts` — 自动判断重试次数（网关模式 1 次，直连模式 3 次）
- `allowed_models` — 直连模式下的模型白名单（逗号分隔的 env 变量）
- `validate()` — 启动时校验配置完整性

#### core/llm_client.py

统一 LLM 客户端。`MyChat` 和 `MyAgent` 共享同一个 `LLMClient` 单例，消除重复的 LLM 初始化、缓存和错误映射代码。

- `get_instance()` — 单例模式获取实例
- `get_llm(model)` — 按模型名懒加载并缓存 `ChatOpenAI` 实例
- `map_error(e)` — 统一的 OpenAI 异常 → 自定义 `LLMError` 映射
- 自动从 `Settings` 读取 `effective_base_url` / `effective_api_key`，网关切换对上层透明

#### core/my_rag.py

RAG 核心服务。主要流程：
1. 接收用户 query + model
2. 从 ChromaDB 中检索相似文档（Top-K=2）
3. 将检索到的文档拼接为 context
4. 调用 MyChat 将 query + context + history + model 传入 LLM 生成回答
5. LLM 调用外层包裹 fallback 兜底，失败时返回友好提示

提供 `query()`（一次性）和 `query_stream()`（流式）两个方法，均返回 `(answer, is_fallback)` 元组。

#### core/my_chat.py

大语言模型封装模块。通过 `LLMClient` 单例获取 ChatOpenAI 实例，支持多模型动态切换。

- `chat(query, model?)` — 普通对话
- `rag_chat(query, context, model?)` — RAG 对话（一次性）
- `rag_chat_stream(query, context, history, model?)` — RAG 对话（流式，支持多轮历史）

均使用 LCEL 链式调用：`prompt | llm | StrOutputParser`。
所有 LLM 调用使用指数退避重试装饰器（直连 3 次 / 网关 1 次，自动适配），鉴权错误不重试。

#### core/my_agent.py

基于 LangGraph 的智能体。通过 `LLMClient` 单例与 MyChat 共享 LLM 配置与缓存，图结构独立演化。

图结构：`START → retrieve (RAG) → agent (LLM+tools) ↔ tools → END`

- RAG 是图的第一个固定节点（不是 tool），每次必检索
- 复用 `retry_utils` 重试降级 + `exceptions` 异常体系
- MemorySaver 持久化会话，`thread_id` 即 `session_id`
- 提供 `chat()` / `chat_stream()` / `get_history()` / `clear_history()`
- 支持通过 `extra_tools` 参数绑定自定义 LangChain Tools

#### core/rag_utils.py

混合重排工具类 `HybridReranker`。与向量库无关，输入为通用 `list[tuple[Document, float]]`。

支持两种融合策略：
- **weighted**：min-max 归一化后按权重加权求和（默认）
- **rrf**：Reciprocal Rank Fusion，基于排名倒数，不依赖分数绝对值

当前未集成到 MyRag 中，留待后续混合检索使用。

### tools/ — Agent 工具层

#### tools/agent_tools.py

Agent 本地工具工厂函数。当前包含 `make_calculator_tool()`（AST 安全解析，支持加减乘除与嵌套表达式，失败抛异常）。新增本地工具时写新的工厂函数，在 `app_server.py` 的 `local_tools` 列表中追加即可。

#### tools/mcp_client.py

MCP（Model Context Protocol）客户端封装模块。桥接外部 MCP over SSE 服务（如 Spring Boot 后端）的工具到 Agent，使 LLM 可以调用外部业务系统的能力。

- `load_all_mcp_tools()` — 加载所有已配置 MCP 服务的工具，返回 `list[BaseTool]`
- `load_mcp_tools_for_service(name)` — 加载单个 MCP 服务的工具
- `shutdown_mcp_clients()` — 关闭连接（供 FastAPI shutdown 钩子调用）
- **优雅降级**：`MCP_ENABLED=false` / SDK 未安装 / 配置缺失 / 连接失败，均返回空工具列表，Agent 正常启动不中断
- 工具通过 `extra_tools` 参数注入 `MyAgent`，与本地工具（calculator）完全等价，统一走 ToolNode + 错误计数机制

### infra/ — 基础设施层

#### infra/exceptions.py

分层异常体系。根类 `RAGBaseException`（含 code / message / status_code / detail）。

- LLM 类：`LLMError` → `LLMAuthError` / `LLMRateLimitError` / `LLMServerError` / `LLMTimeoutError` / `LLMConnectionError`
- 检索类：`RetrieverError` → `VectorStoreInitError` / `EmbeddingModelError`
- 其他：`ValidationError` / `SessionError` / `AgentError` / `MCPError`

#### infra/retry_utils.py

重试与降级工具。

- `with_llm_retry` / `with_llm_retry_stream`：指数退避重试（3次，抖动），可重试错误：限流 / 服务端 / 超时 / 连接
- `with_fallback` / `with_fallback_stream`：捕获 `LLMError` 返回兜底文案

#### infra/langfuse_setup.py

Langfuse 可观测性集成模块。封装 Langfuse CallbackHandler 的创建逻辑，**优雅降级**：未安装 SDK 或缺少环境变量时自动跳过，不影响主流程。

- `get_langfuse_handler(session_id, trace_name, ...)` — 返回 CallbackHandler 或 None
- `build_langchain_metadata(session_id, trace_name, ...)` — 构建 Langfuse trace metadata
- `flush_langfuse()` — 强制 flush 待上报事件
- v4 SDK，自动从环境变量读取密钥，使用 `trace_context` 关联同一次请求内的所有调用

集成范围：
- **普通 RAG 聊天**：retriever 检索 + LLM 链调用分别上报（2 条 trace）
- **Agent 聊天**：LangGraph 图级 callback 自动追踪所有节点（retrieve + agent LLM + tools），单条完整 trace

---

## 项目调用链路

### 普通 RAG 聊天（/chat/stream）

```
用户输入 + 模型选择
   │
   ▼
Vue3 前端 (App.vue)  ← sessionStorage（消息 + session_id + model）
   │  fetch SSE  POST { query, model }
   │  模型列表从 GET /api/models 动态获取
   ▼
Vite 代理 /chat → localhost:8000
   │
   ▼
FastAPI (app_server.py)  ← sessions: { sid: { history, model } }
   │
   ▼
MyRag.query_stream(question, history, model)
   │
   ├─ Retriever (Top-K=2)
   │     └─ ChromaDB + BAAI/bge-small-zh-v1.5
   │
   └─ with_fallback → with_llm_retry（直连 3次 / 网关 1次）
           │
           └─ MyChat.rag_chat_stream()
                   └─ LLMClient.get_llm(model) → ChatOpenAI（共享缓存）
                         │
                         ├─ 直连模式：→ DeepSeek API
                         └─ 网关模式：→ LiteLLM Proxy → 多供应商 / 多 Key
                                       （负载均衡 + 故障转移 + 限流）
```

### Agent 聊天（/agent/chat/stream）

```
用户输入 + 模型选择
   │
   ▼
Vue3 前端（Agent 页面） ← sessionStorage（消息 + session_id + model）
   │  fetch SSE  POST { query, model }
   ▼
Vite 代理 /agent/chat → localhost:8000
   │
   ▼
FastAPI (app_server.py)  ← agent_sessions: { sid: { model } }
   │
   ▼
MyAgent (LangGraph StateGraph)  ← MemorySaver（thread_id = session_id）
   │
   ├─ ① retrieve 节点
   │     └─ 调用 MyRag._retrieve() → ChromaDB
   │
   ├─ ② agent 节点
   │     └─ LLMClient.get_llm(model) + bind_tools（与 MyChat 共享 LLM 缓存）
   │         │
   │         ├─ 直连模式：→ DeepSeek API
   │         └─ 网关模式：→ LiteLLM Proxy → 多供应商 / 多 Key
   │
   └─ ③ tools 节点（有 tool_calls 时循环）
         └─ ToolNode（执行工具，统一入口）
              ├─ 本地工具（agent_tools.py）—— calculator 等
              └─ MCP 工具（mcp_client.py）—— 通过 SSE 调用外部 MCP 服务（如 Spring Boot）
                   └─ 回到 agent 节点
```

---

## LiteLLM 网关

基于 LiteLLM Proxy 的统一 LLM 网关，支持多供应商接入、负载均衡、故障转移、按模型/按 Key 限流、成本统计。Postgres + Redis 架构，单点部署即可平滑升级为集群。

- 两种模式通过 `LITELLM_ENABLED` 环境变量切换，默认关闭（直连模式）
- 应用层透明，开启网关只是换了 `base_url` 和 `api_key`，代码零改动
- 关闭开关立即回到直连模式，1 分钟内回滚

**部署文档：** [`docker-litellm/deploy.md`](docker-litellm/deploy.md) — 包含单点部署、配置说明、限流策略、集群部署、运维命令、数据备份。

---

## Langfuse 可观测性

基于 Langfuse 的全链路可观测性平台，追踪每次 LLM 调用的输入/输出、token 用量、延迟，可视化 RAG 检索和 Agent 工具调用过程。Docker Compose 自托管 6 服务集群（Web + Worker + Postgres + ClickHouse + Redis + MinIO）。

- 优雅降级：未配置或 SDK 不可用时自动跳过，不影响主流程
- Agent 路径：LangGraph 图级 callback 自动传播到所有节点，单次请求一条完整 trace

**部署文档：** [`docker-langfuse/deploy.md`](docker-langfuse/deploy.md) — 包含平台搭建、Python 集成、验证方法、运维命令、数据备份。

---

## Todo List

- [x] **异常处理完善** — 分层异常体系、统一错误码、全局异常处理器、SSE 结构化错误
- [x] **重试降级处理** — LLM 调用指数退避重试（可重试错误 3 次），失败返回兜底文案
- [x] **多模型动态切换** — 前端可选 deepseek-v4-flash / deepseek-v4-pro，会话级绑定，后端按模型名缓存实例
- [x] **混合重排工具类** — 新增 `HybridReranker`，支持加权分数融合与 RRF 两种重排策略，向量库无关
- [x] **LangGraph Agent** — 基于 LangGraph 框架构建 Agent 类，内置 RAG 检索节点 + ReAct 工具循环，支持自定义 Tools，独立于普通 RAG 聊天接口体系
- [x] **本地计算器工具** — Agent 集成 calculator 本地工具（AST 安全计算，支持加减乘除与嵌套表达式），工具错误自动重试，最多 2 次
- [x] **前端路由重构** — 引入 vue-router，拆分 RAG 问答 / Agent 对话两个独立页面，history 模式，顶部滑动切换
- [x] **RAG 检索相似度阈值** — 向量检索增加 similarity_score_threshold=0.3，过滤低相关文档，减少无关上下文干扰
- [x] **Langfuse 集成** — 接入 Langfuse 可观测性平台，Docker Compose 自托管 6 服务集群，Python SDK v4 集成 CallbackHandler，支持 RAG 检索 / LLM 调用 / Agent 工具执行全链路追踪，优雅降级不影响主流程
  - [x] Docker Compose 自托管 Langfuse 平台（web + worker + Postgres + ClickHouse + Redis + MinIO）
  - [x] Python SDK 集成（langfuse_setup.py，CallbackHandler 工厂 + 降级兜底）
  - [x] 普通 RAG 聊天追踪（retriever + LLM chain）
  - [x] Agent 全链路追踪（LangGraph 图级 callback，retrieve + agent + tools 单 trace）
  - [x] 会话维度关联（session_id 透传到 Langfuse trace metadata）
- [x] **Spring Boot MCP 工具集成** — 通过 MCP（Model Context Protocol）桥接 Spring Boot 后端服务，将 Java 侧业务能力（数据库、缓存、业务接口）以工具形式暴露给 Agent 使用
  - [x] langchain-mcp-adapters 适配器，MCP over SSE 工具自动转为 LangChain BaseTool
  - [x] mcp_client.py 封装，支持多服务配置、API Key 认证、超时可配置
  - [x] 优雅降级：MCP 禁用 / SDK 缺失 / 服务不可达，Agent 均正常启动仅用本地工具
- [x] **LiteLLM 统一网关集成** — 接入 LiteLLM Proxy 作为 LLM 网关，支持多供应商统一接入、负载均衡、故障转移、限流、成本统计
  - [x] 统一 LLM 客户端（core/llm_client.py），消除 MyChat / MyAgent 重复代码
  - [x] 集中配置模块（core/config.py），替代散落的 os.getenv
  - [x] 环境变量开关（LITELLM_ENABLED），默认关闭直连模式，零回归风险
  - [x] 动态模型列表：后端 GET /api/models + 前端动态加载，网关模式下从 Proxy 拉取
  - [x] Docker Compose 部署，配置模板含 DeepSeek（启用）+ Ollama/Claude/GPT（注释模板）
  - [x] 双层限流：按模型 RPM/TPM + 按 API Key 并发数
  - [x] 两层重试：网关层 3 次（主）+ 应用层 1 次（备）
- [x] **启动脚本** — scripts/start-backend.sh + scripts/start-frontend.sh，一键启动前后端开发服务
- [ ] **持久化记忆功能** — 将会话历史从内存迁移到持久化存储（如 SQLite / Redis），支持跨重启恢复

---

## 常见问题

**Q: Embedding 模型下载很慢怎么办？**

A: 设置 HuggingFace 镜像后再运行 `pre_load_rag_index.py`：
```bash
export HF_ENDPOINT=https://hf-mirror.com
python pre_load_rag_index.py
```

**Q: 如何更换 LLM 模型？**

A: 修改 `.env` 中的 `OPENAI_MODEL` 和 `OPENAI_API_BASE`，支持所有 OpenAI 兼容接口。

**Q: 如何添加自己的知识库？**

A: 编辑 `pre_load_rag_index.py` 中的 `documents` 列表，替换为你自己的文本内容，然后重新运行脚本。

**Q: 前端启动后端口不是 5173？**

A: Vite 会自动寻找空闲端口。以终端显示的地址为准。
