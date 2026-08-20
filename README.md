# My RAG Service

基于 **LangChain + 本地 Embedding + ChromaDB + FastAPI + Vue3** 构建的 RAG（Retrieval Augmented Generation，检索增强生成）聊天服务。

该项目实现了：

- 本地 Embedding 模型（BAAI/bge-small-zh-v1.5）生成文本向量
- ChromaDB 持久化存储和检索向量数据
- Retriever 根据用户问题召回相关上下文
- 调用大语言模型（DeepSeek / OpenAI 兼容 API）生成最终回答
- 流式输出（SSE），支持逐字渲染
- 多轮对话记忆（服务端 session + 前端 sessionStorage）
- Vue3 + Arco Design + Tailwind 聊天前端界面（微信风格）

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
├── app_server.py              # FastAPI 服务入口
├── my_rag.py                  # RAG 核心业务逻辑
├── my_chat.py                 # 大语言模型封装
├── pre_load_rag_index.py      # 向量数据库初始化脚本
├── main.py                    # 命令行测试入口
│
├── chroma_db/                 # Chroma 向量数据库文件（运行后生成）
├── embeddings/                # 本地 Embedding 模型缓存（运行后自动下载）
│
├── chat-web/                  # Vue3 前端
│   ├── src/
│   │   ├── App.vue            # 聊天页面主组件
│   │   ├── main.js
│   │   └── style.css
│   ├── index.html
│   ├── vite.config.js         # Vite 配置 + 代理
│   ├── tailwind.config.js
│   └── package.json
│
├── .env                       # 环境变量配置
├── requirements.txt           # Python 依赖清单
└── README.md                  # 项目说明文档
```

---

## 技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| LLM 框架 | LangChain | 编排 RAG 流程、Prompt 管理 |
| 嵌入模型 | BAAI/bge-small-zh-v1.5 | 中文 Embedding 模型，本地运行 |
| 向量数据库 | ChromaDB | 轻量级本地向量存储 |
| 大语言模型 | DeepSeek API | 生成回答（OpenAI 兼容，可替换） |
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

**请求体：** `{ "query": "你的问题" }`

**响应：** `{ "query": "...", "answer": "...", "session_id": "..." }`

### `POST /chat/stream`

流式对话（SSE）。支持多轮记忆。

**请求头：** `X-Session-Id`（可选，用于续接会话；不传则新建）

**请求体：** `{ "query": "你的问题" }`

**响应：** `text/event-stream`，事件格式：

```
data: [SESSION] <session_id>   # 第一条消息，返回会话 ID
data: <chunk>                   # 文本片段（多次）
data: [DONE]                    # 结束
data: [ERROR] <message>         # 出错
```

### `GET /chat/history`

获取当前会话历史记录。需要 `X-Session-Id` 请求头。

### `DELETE /chat/history`

清空当前会话历史记录。需要 `X-Session-Id` 请求头。

---

## 前端说明

### 功能特性

- 🎨 微信风格聊天界面
- ⚡ 流式输出，逐字渲染 + 光标闪烁效果
- 💾 会话历史保存在 `sessionStorage`（刷新保留，关闭浏览器丢失）
- 🏷️ 快捷问题标签，点击即问
- 🗑️ 一键清空聊天记录（含二次确认）
- ⌨️ Enter 发送 / Shift+Enter 换行

### 会话机制

- 前端通过 `X-Session-Id` header 与后端会话绑定
- `session_id` 和消息记录存储在 `sessionStorage` 中
- 后端会话存储在内存中，重启后端服务会丢失所有会话
- 每个会话最多保留 20 条消息（10 轮对话）

---

## 核心模块说明

### app_server.py

FastAPI HTTP 服务入口。接收 HTTP 请求，调用 MyRag 服务处理业务逻辑，返回 JSON 或 SSE 流式结果。使用内存字典维护多会话。

### my_rag.py

RAG 核心服务。主要流程：
1. 接收用户 query
2. 从 ChromaDB 中检索相似文档（Top-K=2）
3. 将检索到的文档拼接为 context
4. 调用 MyChat 将 query + context + history 传入 LLM 生成回答

提供 `query()`（一次性）和 `query_stream()`（流式）两个方法。

### my_chat.py

大语言模型封装模块。

- `chat()` — 普通对话
- `rag_chat(query, context)` — RAG 对话（一次性）
- `rag_chat_stream(query, context, history)` — RAG 对话（流式，支持多轮历史）

均使用 LCEL 链式调用：`prompt | llm | StrOutputParser`。

### pre_load_rag_index.py

向量数据库初始化脚本。使用 `RecursiveCharacterTextSplitter`（中文分隔符，chunk_size=200，overlap=20）分割文档并写入 ChromaDB。

---

## 项目调用链路

```
用户输入
   │
   ▼
Vue3 前端 (App.vue)
   │  fetch SSE
   ▼
Vite 代理 /chat → localhost:8000
   │
   ▼
FastAPI (app_server.py)  ← sessions 内存存储
   │
   ▼
MyRag.query_stream(question, history)
   │
   ├─ Retriever (Top-K=2)
   │     └─ ChromaDB + BAAI/bge-small-zh-v1.5
   │
   └─ MyChat.rag_chat_stream()
           └─ ChatOpenAI (DeepSeek API)
                └─ 流式返回
```

---

## Todo List

- [x] **异常处理完善** — 分层异常体系、统一错误码、全局异常处理器、SSE 结构化错误
- [x] **重试降级处理** — LLM 调用指数退避重试（可重试错误 3 次），失败返回兜底文案
- [ ] **持久化记忆功能** — 将会话历史从内存迁移到持久化存储（如 SQLite / Redis），支持跨重启恢复
- [ ] **工具调用** — 集成 Function Calling / Tools，支持查询数据库、调用外部 API 等扩展能力

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
