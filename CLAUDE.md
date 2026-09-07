# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 提供在本仓库中工作的指引。

## 项目概览

一个中文 RAG（检索增强生成）聊天服务，前端为 Vue3。后端使用 LangChain + 本地 Embedding 模型（BAAI/bge-small-zh-v1.5）+ ChromaDB + FastAPI。LLM 使用 OpenAI 兼容接口（默认配置为 DeepSeek，可替换）。包含分层异常体系、LLM 调用指数退避重试、以及 LLM 不可用时的优雅降级兜底。

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
              └─ MyRag.query() / query_stream()
                   ├─ Retriever (ChromaDB + HuggingFace embeddings, top-k=2)
                   └─ with_fallback / with_fallback_stream
                         └─ with_llm_retry / with_llm_retry_stream（3次指数退避重试）
                              └─ MyChat.rag_chat() / rag_chat_stream() → ChatOpenAI + StrOutputParser
```

### 前端

```
Vue3 (App.vue) → fetch SSE /chat/stream → Vite 开发代理 → FastAPI 后端
  Arco Design Vue 组件库
  Tailwind CSS 原子化样式
  sessionStorage 存储消息和 session_id
```

### 核心模块

- **`app_server.py`** — FastAPI 入口。模块加载时初始化 `MyRag` 单例。三层全局异常处理器（RAGBaseException → 结构化 JSON 错误；RequestValidationError → 400；兜底 → 500）。接口：
  - `GET /` — 健康检查
  - `POST /chat` — 一次性 RAG 问答，请求体 `{query: str}`，返回 `{query, answer, session_id, is_fallback?}`
  - `POST /chat/stream` — 流式 RAG（SSE，JSON 结构化事件）。会话通过 `X-Session-Id` 请求头标识。
  - `GET /chat/history` — 获取当前会话历史
  - `DELETE /chat/history` — 清空当前会话历史
- **`my_rag.py`** — `MyRag` 类。加载持久化的 Chroma 向量库，创建 retriever（top-k=2）。`query()` 和 `query_stream()` 均返回 `(结果, is_fallback)` 元组。LLM 调用外层包裹 `with_fallback` / `with_fallback_stream`。
- **`my_chat.py`** — `MyChat` 类。封装 `ChatOpenAI`（启用流式）。方法使用 `@with_llm_retry` / `@with_llm_retry_stream` 装饰器。通过 `_map_openai_error()` 将 OpenAI SDK 异常映射为带类型的 `LLMError` 子类。
- **`exceptions.py`** — 异常体系，根类 `RAGBaseException`。包含 `code`、`message`、`status_code` 和可选的 `detail`。子类：
  - `LLMError`（502）→ `LLMAuthError`、`LLMRateLimitError`（503）、`LLMServerError`、`LLMTimeoutError`（504）、`LLMConnectionError`
  - `RetrieverError`（500）→ `VectorStoreInitError`、`EmbeddingModelError`
  - `ValidationError`（400）、`SessionError`（400）
- **`retry_utils.py`** — 重试和兜底装饰器。`RETRYABLE_ERRORS` = 限流 / 服务端 / 超时 / 连接错误（鉴权错误不重试）。指数退避加抖动，默认 3 次。`with_fallback` 捕获任意 `LLMError`，返回静态兜底文案（`"抱歉，AI 服务暂时繁忙，请稍后再试。"`）并置 `is_fallback=True`。
- **`pre_load_rag_index.py`** — `RagIndexer` 类 + 独立脚本。使用 `RecursiveCharacterTextSplitter` 切分硬编码的 `documents` 列表（中文感知分隔符，chunk_size=200，overlap=20），写入 ChromaDB。

### SSE 事件格式

`/chat/stream` 端点以 `data: {...}\n\n` 格式发送 JSON 结构化事件：

| 类型         | 字段                             | 含义                         |
|-------------|----------------------------------|------------------------------|
| `session`   | `session_id`                     | 第一条消息，返回会话 ID       |
| `text`      | `content`                        | 文本片段（多次事件）          |
| `fallback`  | `message`                        | LLM 调用失败，已使用兜底回复  |
| `error`     | `code`, `message`                | 不可恢复错误                 |
| `done`      | —                                | 流式结束                     |

前端通过对每个 `data:` 行做 `JSON.parse()` 来解析。

### 会话管理

- 后端用内存字典保存会话（`sessions: { session_id: [messages] }`），每个会话最多 20 条消息。
- 前端将 `session_id` 和显示的消息存在 `sessionStorage`（不是 `localStorage`）——刷新页面保留，关闭浏览器丢失。
- 无持久化存储；重启后端会丢失所有会话。

### 已知状态 / 注意事项

- 会话仅在内存中——后端重启 = 所有会话丢失。本地单用户开发不是问题。
- Embedding 模型必须预先缓存在 `embeddings/`；`HF_HUB_OFFLINE=1` 防止启动时访问网络。
- 知识库内容硬编码在 `pre_load_rag_index.py` 的 `__main__` 块中。修改 `documents` 列表后重新运行脚本即可更新。
- 没有测试套件。`pytest` 在 `requirements.txt` 中是注释掉的可选依赖。
- 前端使用 `fetch()` + `ReadableStream` 读取 SSE（不是 `EventSource`）——因为 SSE POST 需要请求体和 `X-Session-Id` 等自定义请求头。
