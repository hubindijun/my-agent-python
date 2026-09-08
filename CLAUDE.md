# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 提供在本仓库中工作的指引。

## 项目概览

一个中文 RAG（检索增强生成）聊天服务，前端为 Vue3。后端使用 LangChain + 本地 Embedding 模型（BAAI/bge-small-zh-v1.5）+ ChromaDB + FastAPI。LLM 使用 OpenAI 兼容接口（默认配置为 DeepSeek，可替换）。包含分层异常体系、LLM 调用指数退避重试、以及 LLM 不可用时的优雅降级兜底。

现已新增 LangGraph Agent：基于 LangGraph StateGraph 的智能体，内置 RAG 检索节点 + ReAct 工具循环，支持自定义 Tools，独立于普通 RAG 聊天。

## 常用命令

### 后端（Python）

```bash
# 安装依赖（conda 环境: mylearn, Python 3.11）
conda activate mylearn
pip install -r requirements.txt

# 初始化 / 重建向量数据库
python pre_load_rag_index.py

# 启动 FastAPI 服务（自动重载）
uvicorn app_server:app --host 0.0.0.0 --port 8000 --reload

# CLI 快速测试（单次非流式查询）
python main.py
```

Swagger UI: `http://localhost:8000/docs`

### 前端（Vue3 + Vite + Arco Design + Tailwind）

```bash
cd chat-web
npm install
npm run dev       # 开发服务器: http://localhost:5173
npm run build     # 生产构建
npm run preview   # 预览生产构建
```

## 环境说明

- Python 3.11，conda 环境 `mylearn`（如沙箱中无法激活 conda，使用 `/Users/hubin/opt/anaconda3/envs/mylearn/bin/python`）
- `.env` 中配置 `OPENAI_API_KEY`、`OPENAI_MODEL`、`OPENAI_API_BASE`（默认 DeepSeek），以及 `HF_HUB_OFFLINE=1` 和 `TRANSFORMERS_OFFLINE=1` 用于离线加载 embedding 模型
- Embedding 模型缓存在 `embeddings/`，ChromaDB 数据在 `chroma_db/`
- 重建向量库：`rm -rf chroma_db && python pre_load_rag_index.py`
- 前端：Node 20 LTS（Node 24 与 esbuild 不兼容）
- 目前没有测试用例

## 架构

### 后端调用链路

```
HTTP 请求 → app_server.py (FastAPI)
              ├─ 全局异常处理器（RAGBaseException / 校验异常 / 兜底）
              ├─ /chat*       → MyRag.query() / query_stream()
              │                    ├─ Retriever (ChromaDB + HuggingFace embeddings, top-k=2)
              │                    └─ with_fallback / with_fallback_stream
              │                         └─ with_llm_retry / with_llm_retry_stream
              │                              └─ MyChat.rag_chat() → ChatOpenAI + StrOutputParser
              └─ /agent/chat* → MyAgent
                                   ├─ LangGraph StateGraph
                                   │    START → retrieve (RAG) → agent (LLM+tools) ↔ tools → END
                                   ├─ MemorySaver 持久化会话
                                   └─ 自有 LLM 实例（独立于 MyChat，便于演化）
```

### 前端

```
Vue3 (App.vue) → fetch SSE /chat/stream → Vite 开发代理 → FastAPI 后端
  Arco Design Vue 组件库
  Tailwind CSS 原子化样式
  sessionStorage 存储消息和 session_id

Agent 模式：独立入口页面，调 /agent/chat/stream，忽略 tool_call/tool_result 事件，渲染体验与普通聊天一致
```

### 核心模块

- **`app_server.py`** — FastAPI 入口。模块加载时初始化 `MyRag` 和 `MyAgent` 单例。三层全局异常处理器。接口：
  - `GET /` — 健康检查
  - `POST /chat` — 一次性 RAG 问答
  - `POST /chat/stream` — 流式 RAG（SSE）
  - `GET /chat/history` / `DELETE /chat/history` — 普通聊天会话历史
  - `POST /agent/chat` — Agent 非流式对话，返回含 `tool_calls` 摘要
  - `POST /agent/chat/stream` — Agent 流式对话（SSE，含 tool_call/tool_result 事件）
  - `GET /agent/chat/history` / `DELETE /agent/chat/history` — Agent 会话历史
- **`my_rag.py`** — `MyRag` 类。加载 Chroma 向量库，retriever top-k=2。`query()` / `query_stream()` 返回 `(结果, is_fallback)`。LLM 调用外层包 `with_fallback`。
- **`my_chat.py`** — `MyChat` 类。封装 `ChatOpenAI`（流式）。方法带 `@with_llm_retry` / `@with_llm_retry_stream` 装饰器。`_map_openai_error()` 映射 OpenAI 异常到自定义 `LLMError` 子类。
- **`my_agent.py`** — `MyAgent` 类。LangGraph StateGraph：retrieve 节点（调用 MyRag._retrieve）+ agent 节点（自有 LLM + tools）+ ToolNode。MemorySaver 做 checkpoint。支持 `chat()` / `chat_stream()` / `get_history()` / `clear_history()`。完全独立于 MyChat，自有 LLM 实例，便于后续演化（子 agent、多模型、复杂图结构）。
- **`agent_tools.py`** — Agent 工具注册辅助。RAG 是内置节点不是 tool，tool 槽位留给业务自定义。
- **`rag_utils.py`** — `HybridReranker` 混合重排工具类。支持 weighted（加权分数融合）和 rrf（Reciprocal Rank Fusion）两种策略。与向量库无关，输入 `list[tuple[Document, float]]`。
- **`exceptions.py`** — 异常体系，根类 `RAGBaseException`。子类：
  - `LLMError`（502）→ `LLMAuthError`、`LLMRateLimitError`（503）、`LLMServerError`、`LLMTimeoutError`（504）、`LLMConnectionError`
  - `RetrieverError`（500）→ `VectorStoreInitError`、`EmbeddingModelError`
  - `AgentError`（500）
  - `ValidationError`（400）、`SessionError`（400）
- **`retry_utils.py`** — 重试和兜底装饰器。`RETRYABLE_ERRORS` = 限流 / 服务端 / 超时 / 连接错误（鉴权错误不重试）。指数退避加抖动，默认 3 次。`with_fallback` 捕获任意 `LLMError` 返回静态兜底文案。
- **`pre_load_rag_index.py`** — `RagIndexer` 类 + 独立脚本。RecursiveCharacterTextSplitter（chunk_size=200，overlap=20）切分 documents，写入 ChromaDB。

### SSE 事件格式

`/chat/stream` 和 `/agent/chat/stream` 均以 `data: {...}\n\n` 格式发送 JSON 结构化事件：

| 类型         | 字段                             | 含义                         | 适用端点 |
|-------------|----------------------------------|------------------------------|----------|
| `session`   | `session_id`, `model`            | 第一条消息，返回会话 ID 和模型 | 两者都有 |
| `text`      | `content`                        | 文本片段（多次事件）          | 两者都有 |
| `fallback`  | `message`                        | LLM 调用失败，已使用兜底回复  | 两者都有 |
| `error`     | `code`, `message`                | 不可恢复错误                 | 两者都有 |
| `done`      | —                                | 流式结束                     | 两者都有 |
| `tool_call` | `name`, `args`                   | Agent 即将调用工具           | 仅 agent |
| `tool_result` | `name`, `content`               | 工具执行完成                 | 仅 agent |

前端通过对每个 `data:` 行做 `JSON.parse()` 来解析。Agent 模式下前端可忽略 tool_call/tool_result 事件。

### 会话管理

- **普通聊天**：后端内存字典 `sessions: { session_id: { history, model } }`，每会话最多 20 条消息。
- **Agent 聊天**：后端内存字典 `agent_sessions: { session_id: { model } }` 存元数据；消息由 LangGraph MemorySaver 持久化，以 `thread_id = session_id` 为 key。
- 两套会话完全隔离，互不污染。
- 前端存储在 `sessionStorage`（刷新保留，关闭浏览器丢失）。
- 无持久化存储；重启后端会丢失所有会话。

### 已知状态 / 注意事项

- 会话仅在内存中——后端重启 = 所有会话丢失。本地单用户开发不是问题。
- Embedding 模型必须预先缓存在 `embeddings/`；`HF_HUB_OFFLINE=1` 防止启动时访问网络。
- 知识库内容硬编码在 `pre_load_rag_index.py` 的 `__main__` 块中。修改 `documents` 列表后重新运行脚本即可更新。
- 没有测试套件。`pytest` 在 `requirements.txt` 中是注释掉的可选依赖。
- 前端使用 `fetch()` + `ReadableStream` 读取 SSE（不是 `EventSource`）——因为 SSE POST 需要请求体和 `X-Session-Id` 等自定义请求头。
- MyAgent 自有 LLM 实例，不依赖 MyChat，便于后续扩展子 agent、多模型、复杂图结构。
- HybridReranker 已实现但尚未集成到 MyRag 或 MyAgent 中，留待后续混合检索使用。
