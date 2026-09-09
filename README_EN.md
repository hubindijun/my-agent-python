# My RAG & Agent Service

An intelligent conversational service built with **LangChain + LangGraph + Local Embedding + ChromaDB + FastAPI + Vue3**, featuring both **RAG (Retrieval Augmented Generation)** and **LangGraph Agent (ReAct tool calling)** capabilities.

Features:

### Common Capabilities
- Local embedding model (BAAI/bge-small-zh-v1.5) for text vectorization
- ChromaDB for persistent vector storage and retrieval
- LLM (DeepSeek / OpenAI-compatible API) generates answers
- **Multi-model dynamic switching** — choose between deepseek-v4-flash / deepseek-v4-pro in the frontend, session-bound
- Streaming output (SSE) with character-by-character rendering
- Multi-turn conversation memory (server-side session + frontend sessionStorage)
- Vue3 + Arco Design + Tailwind chat UI (WeChat-style)
- Layered exception system + exponential backoff retry + graceful fallback

### RAG Chat
- Retriever fetches relevant context based on user queries, LLM generates final answers
- Dedicated `/chat*` endpoint family, stable and reliable

### LangGraph Agent
- Agent built on LangGraph StateGraph, with RAG as the first node in the graph
- ReAct-style tool calling loop, supports binding custom Tools
- MemorySaver for persistent session state, supports resumable conversations
- Dedicated `/agent/chat*` endpoint family, fully isolated from regular RAG
- Own LLM instance, ready for future extension: sub-agents, multi-model, complex graph structures

---

## Table of Contents

- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [API Documentation](#api-documentation)
- [Frontend](#frontend)
- [Core Modules](#core-modules)
- [Call Flow](#call-flow)
- [FAQ](#faq)

---

## Project Structure

```
my/
├── app_server.py              # FastAPI server entry (regular chat + Agent endpoints)
├── my_rag.py                  # RAG core logic (ChromaDB retrieval)
├── my_chat.py                 # Regular chat LLM wrapper (with retry + fallback)
├── my_agent.py                # LangGraph Agent (RAG node + ReAct tool loop)
├── agent_tools.py             # Agent custom tool registration helpers
├── rag_utils.py               # RAG utilities (HybridReranker)
├── exceptions.py              # Hierarchical exception system
├── retry_utils.py             # LLM retry + fallback decorators
├── pre_load_rag_index.py      # Vector DB initialization script
├── main.py                    # CLI test entry point
│
├── chroma_db/                 # Chroma vector DB files (generated at runtime)
├── embeddings/                # Local embedding model cache (auto-downloaded)
│
├── chat-web/                  # Vue3 frontend
│   ├── src/
│   │   ├── App.vue            # Main chat page component
│   │   ├── main.js
│   │   └── style.css
│   ├── index.html             # Regular chat entry
│   ├── agentIndex.html        # Agent chat entry
│   ├── vite.config.js         # Vite config + proxy
│   ├── tailwind.config.js
│   └── package.json
│
├── .env                       # Environment variables
├── requirements.txt           # Python dependencies
├── README.md                  # Documentation (Chinese)
└── README_EN.md               # Documentation (English)
```

---

## Tech Stack

| Category | Technology | Description |
|----------|-----------|-------------|
| LLM Framework | LangChain | RAG orchestration, prompt management |
| Embedding Model | BAAI/bge-small-zh-v1.5 | Chinese embedding model, runs locally |
| Vector Database | ChromaDB | Lightweight local vector store |
| LLM | DeepSeek V4 (Flash / Pro) | Dynamic switching in frontend, OpenAI-compatible API |
| Web Framework | FastAPI | High-performance async HTTP server |
| Frontend | Vue 3 + Vite | Chat UI |
| UI Component Library | Arco Design Vue | Base components |
| Styling | Tailwind CSS | Utility-first CSS |
| Environment | Conda + pip | `mylearn` virtual env (Python 3.11) |

---

## Requirements

- Python >= 3.11
- Node.js >= 20 LTS (Node 24 is incompatible with esbuild)
- Conda (miniconda or anaconda recommended)
- At least 2GB free disk space (for embedding model and vector DB)

---

## Installation

### 1. Create and activate Conda environment

```bash
conda create -n mylearn python=3.11 -y
conda activate mylearn
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Edit the `.env` file:

```env
# LLM config (default: DeepSeek, replace with any OpenAI-compatible API)
OPENAI_API_KEY=your_api_key
OPENAI_MODEL=deepseek-chat
OPENAI_API_BASE=https://api.deepseek.com/v1

# Offline embedding model loading (avoids accessing HuggingFace at startup)
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
```

### 4. Install frontend dependencies

```bash
cd chat-web
npm install
```

---

## Quick Start

### Step 1: Initialize the vector database

On first run, create the knowledge base and generate vector indexes:

```bash
python pre_load_rag_index.py
```

A `chroma_db/` folder will be created on success.

> To rebuild: `rm -rf chroma_db && python pre_load_rag_index.py`

### Step 2: Start the backend server

```bash
uvicorn app_server:app --host 0.0.0.0 --port 8000 --reload
```

### Step 3: Start the frontend

Open a new terminal window:

```bash
cd chat-web
npm run dev
```

Open `http://localhost:5173` in your browser to start chatting.

---

## API Documentation

After starting the backend, visit `http://localhost:8000/docs` for the Swagger UI.

### `GET /`

Health check.

### `POST /chat`

One-shot RAG Q&A.

**Request body:**

```json
{
  "query": "your question",
  "model": "deepseek-v4-flash"
}
```

- `query` (required): User question
- `model` (optional): Model name, choose `deepseek-v4-flash` / `deepseek-v4-pro`; uses session's current model or default if not provided

**Response:** `{ "query": "...", "answer": "...", "session_id": "...", "model": "...", "is_fallback?": true }`

### `POST /chat/stream`

Streaming chat (SSE). Supports multi-turn memory and dynamic model selection.

**Request header:** `X-Session-Id` (optional, for resuming a session; a new one is created if absent)

**Request body:** same as `POST /chat`

**Response:** `text/event-stream`, JSON-structured events (`data: {...}\n\n` format):

| Type | Fields | Description |
|------|--------|-------------|
| `session` | `session_id`, `model` | First message, returns session ID and current model |
| `text` | `content` | Text chunk (multiple events) |
| `fallback` | `message` | LLM call failed, fallback response returned |
| `error` | `code`, `message` | Unrecoverable error |
| `done` | — | Stream ended |

### `GET /chat/history`

Get current session history. Requires `X-Session-Id` header.

### `DELETE /chat/history`

Clear current session history. Requires `X-Session-Id` header.

---

### `POST /agent/chat`

Agent non-streaming chat. Built on LangGraph with built-in RAG retrieval node + ReAct tool loop.

**Request header:** `X-Session-Id` (optional)

**Request body:** same as `POST /chat`

**Response:** `{ "query": "...", "answer": "...", "session_id": "...", "model": "...", "tool_calls?": [...], "is_fallback?": true }`

### `POST /agent/chat/stream`

Agent streaming chat (SSE). Event format is aligned with `/chat/stream`, with additional `tool_call` / `tool_result` events (can be ignored by the frontend).

**Event types:**

| Type | Fields | Description |
|------|--------|-------------|
| `session` | `session_id`, `model` | First message |
| `text` | `content` | Text chunk (multiple events) |
| `tool_call` | `name`, `args` | Agent is calling a tool |
| `tool_result` | `name`, `content` | Tool execution result |
| `fallback` | `message` | LLM failed, fallback used |
| `error` | `code`, `message` | Unrecoverable error |
| `done` | — | Stream ended |

### `GET /agent/chat/history`

Get Agent session history (including tool messages). Requires `X-Session-Id`.

### `DELETE /agent/chat/history`

Clear Agent session history. Requires `X-Session-Id`.

---

## Frontend

### Features

- WeChat-style chat interface
- Model switching — top dropdown for DeepSeek V4 Flash / Pro, session-bound
- Streaming output, character-by-character rendering + cursor blinking
- Session history stored in `sessionStorage` (persists on refresh, lost on browser close)
- Quick question tags — click to ask
- One-click clear chat history (with confirmation)
- Enter to send / Shift+Enter for new line

### Session Mechanism

- Frontend binds to backend session via `X-Session-Id` header
- `session_id`, message history, and **currently selected model** are stored in `sessionStorage`
- Backend sessions are stored in memory with structure `{ history: [...], model: "deepseek-v4-flash" }`; all sessions are lost when the backend restarts
- Each session retains up to 20 messages (10 conversation turns)
- Model selection is session-bound; switching applies to subsequent messages in the same session

---

## Core Modules

### app_server.py

FastAPI HTTP server entry point. Receives HTTP requests, delegates to MyRag/MyAgent for business logic, returns JSON or SSE streaming results.

- Maintains multiple sessions in memory with structure: `{ session_id: { history: [...], model: "deepseek-v4-flash" } }`
- Supports dynamic model switching via `model` parameter in request body
- Three-layer global exception handler: RAGBaseException / validation / fallback
- SSE events in JSON format (`session` / `text` / `fallback` / `error` / `done`)

### my_rag.py

RAG core service. Main flow:
1. Receive user query + model
2. Retrieve similar documents from ChromaDB (Top-K=2)
3. Concatenate retrieved documents into context
4. Call MyChat with query + context + history + model to generate answer
5. LLM call wrapped with fallback, returns friendly message on failure

Provides `query()` (one-shot) and `query_stream()` (streaming), both returning `(answer, is_fallback)` tuples.

### my_chat.py

LLM wrapper module. Supports dynamic multi-model switching, caches `ChatOpenAI` instances by model name.

- `chat(query, model?)` — Regular chat
- `rag_chat(query, context, model?)` — RAG chat (one-shot)
- `rag_chat_stream(query, context, history, model?)` — RAG chat (streaming, multi-turn history)

All use LCEL chains: `prompt | llm | StrOutputParser`.
All LLM calls use exponential backoff retry decorator (3 retries); auth errors are not retried.
OpenAI SDK exceptions are mapped to typed `LLMError` subclasses.

### my_agent.py

LangGraph-based Agent. **Completely independent of MyChat** with its own LLM instance, designed for future evolution (sub-agents, multi-model, complex graph structures).

Graph structure: `START → retrieve (RAG) → agent (LLM+tools) ↔ tools → END`

- RAG is the first fixed node in the graph (not a tool), retrieval always runs
- Reuses `retry_utils` for retry/fallback and `exceptions` for error hierarchy
- MemorySaver persists sessions; `thread_id` maps to `session_id`
- Provides `chat()` / `chat_stream()` / `get_history()` / `clear_history()`
- Supports binding custom LangChain Tools via the `extra_tools` parameter

### rag_utils.py

Hybrid reranking utility class `HybridReranker`. Vector-DB-agnostic, takes generic `list[tuple[Document, float]]` as input.

Supports two fusion strategies:
- **weighted**: Weighted sum after min-max normalization (default)
- **rrf**: Reciprocal Rank Fusion, rank-based, score-agnostic

Currently not integrated into MyRag, reserved for future hybrid search.

### exceptions.py

Layered exception system. Root class `RAGBaseException` (with code / message / status_code / detail).

- LLM: `LLMError` → `LLMAuthError` / `LLMRateLimitError` / `LLMServerError` / `LLMTimeoutError` / `LLMConnectionError`
- Retriever: `RetrieverError` → `VectorStoreInitError` / `EmbeddingModelError`
- Other: `ValidationError` / `SessionError` / `AgentError`

### retry_utils.py

Retry and fallback utilities.

- `with_llm_retry` / `with_llm_retry_stream`: Exponential backoff retry (3x, with jitter). Retryable errors: rate limit / server error / timeout / connection
- `with_fallback` / `with_fallback_stream`: Catch `LLMError` and return fallback message

### pre_load_rag_index.py

Vector database initialization script. Uses `RecursiveCharacterTextSplitter` (Chinese-aware separators, chunk_size=200, overlap=20) to split documents and writes them to ChromaDB.

---

## Call Flow

### Regular RAG Chat (`/chat/stream`)

```
User input + model selection
   │
   ▼
Vue3 Frontend (App.vue)  ← sessionStorage (messages + session_id + model)
   │  fetch SSE  POST { query, model }
   ▼
Vite proxy /chat → localhost:8000
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
   └─ with_fallback → with_llm_retry (3x exponential backoff)
           │
           └─ MyChat.rag_chat_stream()
                   └─ ChatOpenAI (cached by model name)
                         └─ streaming response
```

### Agent Chat (`/agent/chat/stream`)

```
User input + model selection
   │
   ▼
Vue3 Frontend (Agent page)  ← sessionStorage (messages + session_id + model)
   │  fetch SSE  POST { query, model }
   ▼
Vite proxy /agent/chat → localhost:8000
   │
   ▼
FastAPI (app_server.py)  ← agent_sessions: { sid: { model } }
   │
   ▼
MyAgent (LangGraph StateGraph)  ← MemorySaver (thread_id = session_id)
   │
   ├─ ① retrieve node
   │     └─ calls MyRag._retrieve() → ChromaDB
   │
   ├─ ② agent node
   │     └─ owned ChatOpenAI + bind_tools
   │         └─ with_llm_retry (3x exponential backoff)
   │
   └─ ③ tools node (loops when there are tool_calls)
         └─ ToolNode (executes custom tools)
              └─ back to agent node
```

---

## Todo List

- [x] **Exception handling** — Layered exception system, unified error codes, global exception handler, SSE structured errors
- [x] **Retry & fallback** — Exponential backoff retry for LLM calls (3 retries for retryable errors), fallback message on failure
- [x] **Multi-model dynamic switching** — Choose deepseek-v4-flash / deepseek-v4-pro in frontend, session-bound, backend caches instances by model name
- [x] **Hybrid reranker utility** — Added `HybridReranker`, supports weighted score fusion and RRF strategies, vector-DB-agnostic
- [x] **LangGraph Agent** — Agent class built on LangGraph, with built-in RAG retrieval node + ReAct tool loop, supports custom Tools, isolated from regular RAG chat endpoints
- [x] **Local calculator tool** — Agent integrates calculator local tool (AST-safe evaluation, supports +-*/ and nested expressions), with auto-retry on tool errors (max 2 retries)
- [x] **Frontend router refactor** — Introduced vue-router, split into RAG chat / Agent chat pages, history mode, top pill-style switcher
- [x] **RAG similarity threshold** — Added similarity_score_threshold=0.3 to vector retrieval, filtering low-relevance documents to reduce noisy context
- [ ] **LangFuse integration** — Integrate LangFuse observability platform to trace full LLM call chains, RAG retrieval, and Agent tool execution, with latency/cost/quality analytics
- [ ] **Spring Boot MCP tool integration** — Bridge Spring Boot backend services via MCP (Model Context Protocol), expose Java-side business capabilities (database, cache, business APIs) to the Agent as tools
- [ ] **Persistent memory** — Migrate session history from in-memory to persistent storage (SQLite / Redis), survive restarts

---

## FAQ

**Q: Embedding model download is very slow. What can I do?**

A: Set the HuggingFace mirror before running `pre_load_rag_index.py`:
```bash
export HF_ENDPOINT=https://hf-mirror.com
python pre_load_rag_index.py
```

**Q: How do I change the LLM model?**

A: Modify `OPENAI_MODEL` and `OPENAI_API_BASE` in `.env`. All OpenAI-compatible APIs are supported.

**Q: How do I add my own knowledge base?**

A: Edit the `documents` list in `pre_load_rag_index.py`, replace with your own text content, then re-run the script.

**Q: The frontend starts on a different port than 5173?**

A: Vite automatically finds an available port. Use the address shown in the terminal.
