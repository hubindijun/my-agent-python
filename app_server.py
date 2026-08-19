from dotenv import load_dotenv
load_dotenv()

import uuid
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from my_rag import MyRag

app = FastAPI(title="My RAG Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag = MyRag()

# 内存中存储会话历史：{ session_id: [ {role, content}, ... ] }
sessions = {}
MAX_HISTORY_PER_SESSION = 20  # 每个会话最多保留 20 条（10 轮）


def get_session_id(request: Request) -> str:
    """从 header 中获取 session_id，没有则新建"""
    session_id = request.headers.get("X-Session-Id")
    if not session_id:
        session_id = str(uuid.uuid4())
    if session_id not in sessions:
        sessions[session_id] = []
    return session_id


def add_history(session_id: str, role: str, content: str):
    history = sessions[session_id]
    history.append({"role": role, "content": content})
    # 超过上限时裁剪最旧的
    if len(history) > MAX_HISTORY_PER_SESSION:
        sessions[session_id] = history[-MAX_HISTORY_PER_SESSION:]


class QueryRequest(BaseModel):
    query: str


class StreamRequest(BaseModel):
    query: str


@app.get("/")
def index():
    return {"message": "RAG service running"}


@app.post("/chat")
def chat(request: QueryRequest, req: Request):
    session_id = get_session_id(req)
    add_history(session_id, "user", request.query)
    answer = rag.query(request.query)
    add_history(session_id, "assistant", answer)
    return {"query": request.query, "answer": answer, "session_id": session_id}


@app.get("/chat/history")
def get_history(req: Request):
    """获取当前会话的历史记录"""
    session_id = req.headers.get("X-Session-Id")
    if not session_id or session_id not in sessions:
        return {"history": [], "session_id": session_id or str(uuid.uuid4())}
    return {"history": sessions[session_id], "session_id": session_id}


@app.delete("/chat/history")
def clear_history(req: Request):
    """清空当前会话的历史记录"""
    session_id = req.headers.get("X-Session-Id")
    if session_id and session_id in sessions:
        sessions[session_id] = []
    return {"ok": True}


@app.post("/chat/stream")
async def chat_stream(request: StreamRequest, req: Request):
    """流式对话接口（SSE），服务端维护会话历史"""

    session_id = get_session_id(req)
    add_history(session_id, "user", request.query)

    # 取最近的历史（不含刚加的用户消息，stream 里会一起传）
    history = sessions[session_id][:-1]

    async def event_generator():
        full_answer = ""
        try:
            # 先发 session_id，让前端知道
            yield f"data: [SESSION] {session_id}\n\n"

            for chunk in rag.query_stream(request.query, history):
                if chunk:
                    full_answer += chunk
                    yield f"data: {chunk}\n\n"

            # 存到历史
            add_history(session_id, "assistant", full_answer)
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Session-Id": session_id,
        },
    )
