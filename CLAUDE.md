# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

一个中文 RAG（检索增强生成）聊天服务，前端为 Vue3。后端使用 LangChain + 本地 Embedding 模型（BAAI/bge-small-zh-v1.5）+ ChromaDB + FastAPI。LLM 使用 OpenAI 兼容接口（默认配置为 DeepSeek，可替换）。包含分层异常体系、LLM 调用指数退避重试、以及 LLM 不可用时的优雅降级兜底。

现已新增 LangGraph Agent：基于 LangGraph StateGraph 的智能体，内置 RAG 检索节点 + ReAct 工具循环，支持自定义 Tools，独立于普通 RAG 聊天。已集成 calculator 本地工具作为示例。

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

### 前端（Vue3 + Vite + Arco Design + Tailwind + vue-router）

```bash
cd chat-web
npm install
npm run dev       # 开发服务器: http://localhost:5173
npm run build     # 生产构建
npm run preview   # 预览生产构建
```

页面路由：
- `/` — RAG 智能问答（普通聊天）
- `/agent` — Agent 智能对话（工具调用）

## 环境说明

- Python 3.11，conda 环境 `mylearn`（如沙箱中无法激活 conda，使用 `/Users/hubin/opt/anaconda3/envs/mylearn/bin/python`）
- `.env` 中配置 `OPENAI_API_KEY`、`OPENAI_MODEL`、`OPENAI_API_BASE`（默认 DeepSeek），以及 `HF_HUB_OFFLINE=1` 和 `TRANSFORMERS_OFFLINE=1` 用于离线加载 embedding 模型
- Embedding 模型缓存在 `embeddings/`，ChromaDB 数据在 `chroma_db/`
- 重建向量库：`rm -rf chroma_db && python pre_load_rag_index.py`
- 前端：Node 20 LTS（Node 24 与 esbuild 不兼容）
- 目前没有测试用例。`pytest` 在 `requirements.txt` 中是注释掉的可选依赖

## 架构

### 后端调用链路

```
HTTP 请求 → app_server.py (FastAPI)
              ├─ 全局异常处理器（RAGBaseException / 校验异常 / 兜底）
              ├─ /chat*       → MyRag.query() / query_stream()
              │                    ├─ Retriever (ChromaDB + BGE embeddings, top-k=2, score_threshold=0.3)
              │                    └─ with_fallback / with_fallback_stream
              │                         └─ with_llm_retry / with_llm_retry_stream
              │                              └─ MyChat.rag_chat() → ChatOpenAI + StrOutputParser
              └─ /agent/chat* → MyAgent
                                   ├─ LangGraph StateGraph
                                   │    START → retrieve (RAG) → agent (LLM+tools) ↔ tools → END
                                   │    tool_error_count 达到 MAX_TOOL_RETRIES(2) 强制 end
                                   ├─ MemorySaver 持久化会话
                                   ├─ 自有 LLM 实例（独立于 MyChat）
                                   └─ 工具（两层，统一注入 extra_tools）
                                        ├─ 本地工具: calculator 等（agent_tools.py）
                                        └─ MCP 工具: 外部 MCP over SSE 服务动态加载（mcp_client.py）
                                             └─ 服务配置: _SERVICES 列表 + .env MCP_<NAME>_*
```

### 前端架构

```
index.html → main.js → App.vue (顶部布局 + 模型选择 + 清空)
                              └─ <router-view />
                                    ├─ /       → views/ChatRAG.vue    → fetch SSE /chat/stream
                                    └─ /agent  → views/ChatAgent.vue  → fetch SSE /agent/chat/stream
  Arco Design Vue 组件库
  Tailwind CSS 原子化样式
  vue-router 4，history 模式
  Vite historyApiFallback 支持
  sessionStorage 存储消息和 session_id（每个页面独立存储）
```

前端使用 `fetch()` + `ReadableStream` 读取 SSE（不是 `EventSource`）——因为 SSE POST 需要请求体和 `X-Session-Id` 等自定义请求头。

Agent 页面忽略 `tool_call` / `tool_result` 事件，只渲染 `text` 事件，体验与普通聊天一致。

### 核心模块

- **`app_server.py`** — FastAPI 入口。模块加载时初始化 `MyRag` 和 `MyAgent` 单例（Agent 绑定 calculator 工具）。三层全局异常处理器。
- **`my_rag.py`** — `MyRag` 类。Chroma 向量库，retriever 使用 `similarity_score_threshold`（k=2, threshold=0.3），低于阈值的文档被过滤。`query()` / `query_stream()` 返回 `(结果, is_fallback)`。LLM 调用外层包 `with_fallback`。
- **`my_chat.py`** — `MyChat` 类。封装 `ChatOpenAI`（流式）。方法带 `@with_llm_retry` / `@with_llm_retry_stream` 装饰器。`_map_openai_error()` 映射 OpenAI 异常到自定义 `LLMError` 子类。
- **`my_agent.py`** — `MyAgent` 类。LangGraph StateGraph：retrieve 节点（调用 MyRag._retrieve）+ agent 节点（自有 LLM + tools）+ `_tools_node` 包装层（错误计数，MAX_TOOL_RETRIES=2 次后强制结束）。MemorySaver 做 checkpoint。完全独立于 MyChat，自有 LLM 实例。
- **`agent_tools.py`** — Agent 本地工具工厂函数。当前只有 `make_calculator_tool()`（AST 安全解析，支持加减乘除与嵌套表达式，失败抛异常）。新增本地工具时写新的工厂函数，在 `app_server.py` 的 `local_tools` 列表中追加即可。
- **`mcp_client.py`** — MCP 客户端封装。通过 `langchain-mcp-adapters` 将 MCP over SSE 服务的工具桥接到 Agent。优雅降级：`MCP_ENABLED=false` / SDK 缺失 / 配置缺失 / 服务不可达，均返回空工具列表，Agent 正常启动。支持多服务配置（`_SERVICES` 列表 + `.env` 中 `MCP_<NAME>_URL/TIMEOUT/API_KEY`）。每次工具调用独立建立 SSE 连接，天然支持重连。
- **`langfuse_setup.py`** — Langfuse 可观测性集成。CallbackHandler 工厂，优雅降级（SDK 未装或配置缺失时返回 None，不影响主流程）。
- **`rag_utils.py`** — `HybridReranker` 混合重排工具类。支持 weighted 和 rrf 两种策略。尚未集成到 MyRag 或 MyAgent 中。
- **`exceptions.py`** — 分层异常体系，根类 `RAGBaseException`。
- **`retry_utils.py`** — LLM 调用重试 + 兜底装饰器。可重试错误：限流 / 服务端 / 超时 / 连接（鉴权错误不重试）。默认 3 次指数退避。

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

### 会话管理

- **普通聊天**：后端内存字典 `sessions: { session_id: { history, model } }`，每会话最多 20 条消息。前端 sessionStorage key: `rag_chat_session` / `rag_session_id`。
- **Agent 聊天**：后端内存字典 `agent_sessions: { session_id: { model } }` 存元数据；消息由 LangGraph MemorySaver 持久化，以 `thread_id = session_id` 为 key。前端 sessionStorage key: `agent_chat_session` / `agent_session_id`。
- 两套会话完全隔离，互不污染。
- 无持久化存储；重启后端会丢失所有会话。

### 新增 Agent 工具的方式

工具分两类，注册方式不同：

**本地工具**（Python 代码实现，如 calculator）：
1. 在 `agent_tools.py` 中新增 `make_xxx_tool()` 工厂函数，返回 `BaseTool`
2. 在 `app_server.py` 的 `local_tools` 列表中追加新工具
3. 工具失败应**抛异常**（不要返回错误字符串）——ToolNode 会自动捕获并生成 `is_error=True` 的 ToolMessage，`_tools_node` 计入错误计数

**MCP 工具**（外部 MCP over SSE 服务提供，如 Spring Boot）：
1. 在 `mcp_client.py` 的 `_SERVICES` 列表中追加服务名（大写，如 `"SPRINGBOOT"`）
2. 在 `.env` 中添加对应配置：
   - `MCP_<NAME>_URL` — MCP SSE 端点地址（必填）
   - `MCP_<NAME>_TIMEOUT` — 连接超时秒数（可选，默认 10）
   - `MCP_<NAME>_API_KEY` — API 密钥（可选，空则不启用认证）
3. `app_server.py` 的 `load_all_mcp_tools()` 会自动加载，无需手动导入
4. MCP 全局开关：`MCP_ENABLED=true`（默认开启，设为 false 全部禁用）

两类工具最终都合并到 `extra_tools` 注入 `MyAgent`，Agent 内部无区别，统一走 ToolNode + 错误计数机制。

### 已知状态 / 注意事项

- 会话仅在内存中——后端重启 = 所有会话丢失。本地单用户开发不是问题。
- Embedding 模型必须预先缓存在 `embeddings/`；`HF_HUB_OFFLINE=1` 防止启动时访问网络。
- 知识库内容硬编码在 `pre_load_rag_index.py` 的 `__main__` 块中。修改 `documents` 列表后重新运行脚本即可更新。
- HybridReranker 已实现但尚未集成到 MyRag 或 MyAgent 中，留待后续混合检索使用。
- MCP 工具为按需连接模式（每次调用独立建立 SSE 连接），无持久长连接；优点是天然支持重连、无连接管理复杂度，缺点是每次调用有连接开销。工具调用频率不高的场景完全够用。
- `langchain-mcp-adapters 0.1.x` 依赖 `mcp 1.x`；`mcp 2.x` 有破坏性变更（`fastmcp` 改名等），requirements.txt 已锁定 `mcp<2.0.0`。
