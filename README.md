# My RAG & Agent Service

基于 **LangChain + LangGraph + 本地 Embedding + ChromaDB + FastAPI + Vue3** 构建的智能对话服务，包含 **RAG 检索增强生成** 与 **LangGraph Agent（ReAct 工具调用）** 两套能力。

该项目实现了：

### 通用能力
- 本地 Embedding 模型（BAAI/bge-small-zh-v1.5）生成文本向量
- ChromaDB 持久化存储和检索向量数据
- 调用大语言模型（DeepSeek / OpenAI 兼容 API）生成回答
- **多模型动态切换** — 前端可选 deepseek-v4-flash / deepseek-v4-pro，会话级绑定
- 流式输出（SSE），支持逐字渲染
- 多轮对话记忆（服务端 session + 前端 sessionStorage）
- Vue3 + Arco Design + Tailwind 聊天前端界面（微信风格）
- 分层异常体系 + 指数退避重试 + 优雅降级兜底

### RAG 聊天
- Retriever 根据用户问题召回相关上下文，交由 LLM 生成最终回答
- 独立的 `/chat*` 接口体系，稳定可靠

### LangGraph Agent
- 基于 LangGraph StateGraph 构建的智能体，RAG 作为图的第一个节点
- ReAct 模式的工具调用循环，支持绑定自定义 Tools
- MemorySaver 持久化会话状态，支持断点续聊
- 独立的 `/agent/chat*` 接口体系，与普通 RAG 完全隔离
- 自有 LLM 实例，便于后续扩展子 Agent、多模型、复杂图结构

---

## 目录

- [项目结构](#项目结构)
- [技术栈](#技术栈)
- [环境要求](#环境要求)
- [安装部署](#安装部署)
- [快速开始](#快速开始)
- [API 文档](#api-文档)
- [前端说明](#前端说明)
- [核心模块说明](#核心模块说明)
- [项目调用链路](#项目调用链路)

---

## 项目结构

```
my/
├── app_server.py              # FastAPI 服务入口（普通聊天 + Agent 接口）
├── my_rag.py                  # RAG 核心业务逻辑（ChromaDB 检索）
├── my_chat.py                 # 普通聊天 LLM 封装（带重试 + 兜底）
├── my_agent.py                # LangGraph Agent（RAG 节点 + ReAct 工具循环）
├── agent_tools.py             # Agent 自定义工具注册辅助
├── rag_utils.py               # RAG 工具类（HybridReranker 混合重排）
├── exceptions.py              # 分层异常体系
├── retry_utils.py             # LLM 调用重试 + 兜底装饰器
├── pre_load_rag_index.py      # 向量数据库初始化脚本
├── main.py                    # 命令行测试入口
│
├── chroma_db/                 # Chroma 向量数据库文件（运行后生成）
├── embeddings/                # 本地 Embedding 模型缓存（运行后自动下载）
│
├── chat-web/                  # Vue3 前端
│   ├── src/
│   │   ├── App.vue            # 普通聊天页面主组件
│   │   ├── main.js
│   │   └── style.css
│   ├── index.html             # 普通聊天入口
│   ├── agentIndex.html        # Agent 聊天入口
│   ├── vite.config.js         # Vite 配置 + 代理
│   ├── tailwind.config.js
│   └── package.json
│
├── .env                       # 环境变量配置
├── requirements.txt           # Python 依赖清单
├── README.md                  # 项目说明文档
└── README_EN.md               # English documentation
```

---

## 技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| LLM 框架 | LangChain | 编排 RAG 流程、Prompt 管理 |
| 嵌入模型 | BAAI/bge-small-zh-v1.5 | 中文 Embedding 模型，本地运行 |
| 向量数据库 | ChromaDB | 轻量级本地向量存储 |
| 大语言模型 | DeepSeek V4 (Flash / Pro) | 支持前端动态切换，OpenAI 兼容接口 |
| Web 框架 | FastAPI | 高性能异步 HTTP 服务 |
| 前端框架 | Vue 3 + Vite | 聊天界面 |
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
# LLM 配置（默认 DeepSeek，可替换为任意 OpenAI 兼容接口）
OPENAI_API_KEY=你的_api_key
OPENAI_MODEL=deepseek-chat
OPENAI_API_BASE=https://api.deepseek.com/v1

# Embedding 模型离线加载（避免启动时访问 HuggingFace）
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
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

```bash
uvicorn app_server:app --host 0.0.0.0 --port 8000 --reload
```

### 第三步：启动前端

新开一个终端窗口：

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

### app_server.py

FastAPI HTTP 服务入口。接收 HTTP 请求，调用 MyRag 服务处理业务逻辑，返回 JSON 或 SSE 流式结果。

- 使用内存字典维护多会话，结构：`{ session_id: { history: [...], model: "deepseek-v4-flash" } }`
- 支持请求体传 `model` 参数动态切换模型（可选 `deepseek-v4-flash` / `deepseek-v4-pro`）
- 三层全局异常处理器：RAGBaseException / 校验异常 / 兜底异常
- SSE 事件为 JSON 结构化格式（`session` / `text` / `fallback` / `error` / `done`）

### my_rag.py

RAG 核心服务。主要流程：
1. 接收用户 query + model
2. 从 ChromaDB 中检索相似文档（Top-K=2）
3. 将检索到的文档拼接为 context
4. 调用 MyChat 将 query + context + history + model 传入 LLM 生成回答
5. LLM 调用外层包裹 fallback 兜底，失败时返回友好提示

提供 `query()`（一次性）和 `query_stream()`（流式）两个方法，均返回 `(answer, is_fallback)` 元组。

### my_chat.py

大语言模型封装模块。支持多模型动态切换，按模型名缓存 `ChatOpenAI` 实例。

- `chat(query, model?)` — 普通对话
- `rag_chat(query, context, model?)` — RAG 对话（一次性）
- `rag_chat_stream(query, context, history, model?)` — RAG 对话（流式，支持多轮历史）

均使用 LCEL 链式调用：`prompt | llm | StrOutputParser`。
所有 LLM 调用使用指数退避重试装饰器（3次），鉴权错误不重试。
OpenAI SDK 异常映射为带类型的 `LLMError` 子类。

### exceptions.py

分层异常体系。根类 `RAGBaseException`（含 code / message / status_code / detail）。

- LLM 类：`LLMError` → `LLMAuthError` / `LLMRateLimitError` / `LLMServerError` / `LLMTimeoutError` / `LLMConnectionError`
- 检索类：`RetrieverError` → `VectorStoreInitError` / `EmbeddingModelError`
- 其他：`ValidationError` / `SessionError`

### retry_utils.py

重试与降级工具。

- `with_llm_retry` / `with_llm_retry_stream`：指数退避重试（3次，抖动），可重试错误：限流 / 服务端 / 超时 / 连接
- `with_fallback` / `with_fallback_stream`：捕获 `LLMError` 返回兜底文案

### my_agent.py

基于 LangGraph 的智能体。**完全独立于 MyChat**，自有 LLM 实例，便于后续演化（子 agent、多模型、复杂图结构）。

图结构：`START → retrieve (RAG) → agent (LLM+tools) ↔ tools → END`

- RAG 是图的第一个固定节点（不是 tool），每次必检索
- 复用 `retry_utils` 重试降级 + `exceptions` 异常体系
- MemorySaver 持久化会话，`thread_id` 即 `session_id`
- 提供 `chat()` / `chat_stream()` / `get_history()` / `clear_history()`
- 支持通过 `extra_tools` 参数绑定自定义 LangChain Tools

### rag_utils.py

混合重排工具类 `HybridReranker`。与向量库无关，输入为通用 `list[tuple[Document, float]]`。

支持两种融合策略：
- **weighted**：min-max 归一化后按权重加权求和（默认）
- **rrf**：Reciprocal Rank Fusion，基于排名倒数，不依赖分数绝对值

当前未集成到 MyRag 中，留待后续混合检索使用。

### pre_load_rag_index.py

向量数据库初始化脚本。使用 `RecursiveCharacterTextSplitter`（中文分隔符，chunk_size=200，overlap=20）分割文档并写入 ChromaDB。

---

## 项目调用链路

### 普通 RAG 聊天（/chat/stream）

```
用户输入 + 模型选择
   │
   ▼
Vue3 前端 (App.vue)  ← sessionStorage（消息 + session_id + model）
   │  fetch SSE  POST { query, model }
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
   └─ with_fallback → with_llm_retry (3次指数退避)
           │
           └─ MyChat.rag_chat_stream()
                   └─ ChatOpenAI（按模型名缓存实例）
                         └─ 流式返回
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
   │     └─ 自有 ChatOpenAI + bind_tools
   │         └─ with_llm_retry (3次指数退避)
   │
   └─ ③ tools 节点（有 tool_calls 时循环）
         └─ ToolNode（执行自定义工具）
              └─ 回到 agent 节点
```

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
- [ ] **LangFuse 集成** — 接入 LangFuse 可观测性平台，追踪 LLM 调用、RAG 检索、Agent 工具执行的完整链路，支持耗时/成本/质量分析
- [ ] **Spring Boot MCP 工具集成** — 通过 MCP（Model Context Protocol）桥接 Spring Boot 后端服务，将 Java 侧业务能力（数据库、缓存、业务接口）以工具形式暴露给 Agent 使用
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
