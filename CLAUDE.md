# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Chinese-language RAG (Retrieval Augmented Generation) service with a Vue3 chat frontend. Backend uses LangChain + local Embedding (BAAI/bge-small-zh-v1.5) + ChromaDB + FastAPI. LLM uses OpenAI-compatible APIs (configured for DeepSeek, swappable).

## Commands

### Backend (Python)

```bash
# Install dependencies (conda env: mylearn, Python 3.11)
conda activate mylearn
pip install -r requirements.txt

# Initialize / rebuild the vector database
python pre_load_rag_index.py

# Start the FastAPI server with auto-reload
uvicorn app_server:app --host 0.0.0.0 --port 8000 --reload

# CLI quick test
python main.py
```

Swagger UI: `http://localhost:8000/docs`

### Frontend (Vue3 + Vite)

```bash
cd chat-web
npm install
npm run dev       # dev server at http://localhost:5173
npm run build     # production build
```

## Environment

- Python 3.11, conda environment `mylearn` (use `/Users/hubin/opt/anaconda3/envs/mylearn/bin/python` if conda activation fails in sandbox)
- `.env` holds `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_API_BASE` (DeepSeek by default), plus `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` for local-only embedding model loading
- Embedding model cached in `embeddings/`, ChromaDB in `chroma_db/`
- To rebuild the vector store: `rm -rf chroma_db && python pre_load_rag_index.py`
- Frontend: Node 20 LTS (Node 24 is incompatible with esbuild)

## Architecture

### Backend call chain

```
HTTP request → app_server.py (FastAPI) → MyRag.query() / query_stream()
                                           ├─ Retriever (ChromaDB + HuggingFace embeddings, top-k=2)
                                           └─ MyChat.rag_chat() / rag_chat_stream() → ChatOpenAI + StrOutputParser
```

### Frontend

```
Vue3 (App.vue) → SSE fetch /chat/stream → Vite dev proxy → FastAPI backend
```

### Key modules

- **`app_server.py`** — FastAPI entry point. `MyRag` singleton initialized at module load. Endpoints:
  - `GET /` — health check
  - `POST /chat` — one-shot RAG query, body `{query: str}`, returns `{query, answer, session_id}`
  - `POST /chat/stream` — streaming RAG via SSE, body `{query: str}`, returns chunks as `data: ...` events. Session identified by `X-Session-Id` header. Events: `[SESSION] <id>`, text chunks, `[DONE]`, `[ERROR] <msg>`
  - `GET /chat/history` — get current session history (by `X-Session-Id`)
  - `DELETE /chat/history` — clear current session history
- **`my_rag.py`** — `MyRag` class. Loads persisted Chroma vector store, creates retriever (top-k=2). Methods: `query()` and `query_stream(question, history)`.
- **`my_chat.py`** — `MyChat` class. Wraps `ChatOpenAI` (streaming enabled). Methods: `chat()`, `rag_chat(query, context)`, `rag_chat_stream(query, context, history)` — the streaming variant supports multi-turn history via `MessagesPlaceholder`.
- **`pre_load_rag_index.py`** — `RagIndexer` class + standalone script. Splits hardcoded `documents` list with `RecursiveCharacterTextSplitter` (Chinese-aware, chunk_size=200, overlap=20) and writes to ChromaDB.

### Frontend files

- **`chat-web/src/App.vue`** — single component chat UI (WeChat-style). Features: streaming output with blinking cursor, `sessionStorage`-backed history (survives refresh, cleared on browser close), quick-question tags, clear-history button with confirm.
- **`chat-web/vite.config.js`** — Vite config, proxies `/chat` → `http://localhost:8000`.
- Session maintained client-side via `X-Session-Id` header (stored in `sessionStorage`, sent with each request).

### Session management

- Backend keeps sessions in a memory dict (`sessions: { session_id: [messages] }`), max 20 messages per session.
- Frontend stores `session_id` and displayed messages in `sessionStorage` (not `localStorage`) — persists across page refresh but not browser restart.
- No persistence to disk; restarting the backend loses all sessions.

### Known state / caveats

- Sessions are in-memory only — backend restart = all sessions lost. Not a problem for single-user local dev.
- Embedding model must be pre-cached in `embeddings/`; `HF_HUB_OFFLINE=1` prevents network calls at startup.
- Knowledge base content is hardcoded in `pre_load_rag_index.py`'s `__main__` block. Edit the `documents` list and re-run to update.
