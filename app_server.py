import json
import logging
import uuid

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, field_validator

from exceptions import RAGBaseException, ValidationError, AgentError
from my_rag import MyRag
from my_agent import MyAgent
from agent_tools import make_calculator_tool

ALLOWED_MODELS = ["deepseek-v4-flash", "deepseek-v4-pro"]
DEFAULT_MODEL = "deepseek-v4-flash"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app_server")

app = FastAPI(title="My RAG Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag = MyRag()
agent = MyAgent(rag, extra_tools=[make_calculator_tool()])

sessions: dict[str, dict] = {}
agent_sessions: dict[str, dict] = {}
MAX_HISTORY_PER_SESSION = 20


def get_session_id(request: Request) -> str:
    session_id = request.headers.get("X-Session-Id")
    if not session_id:
        session_id = str(uuid.uuid4())
    if session_id not in sessions:
        sessions[session_id] = {
            "history": [],
            "model": DEFAULT_MODEL,
        }
    return session_id


def add_history(session_id: str, role: str, content: str):
    history = sessions[session_id]["history"]
    history.append({"role": role, "content": content})
    if len(history) > MAX_HISTORY_PER_SESSION:
        sessions[session_id]["history"] = history[-MAX_HISTORY_PER_SESSION:]


def set_session_model(session_id: str, model: str | None):
    if model and model in ALLOWED_MODELS:
        sessions[session_id]["model"] = model


class QueryRequest(BaseModel):
    query: str
    model: str | None = None

    @field_validator("query")
    @classmethod
    def query_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("query 不能为空")
        return v.strip()

    @field_validator("model")
    @classmethod
    def model_must_be_allowed(cls, v):
        if v is None:
            return v
        if v not in ALLOWED_MODELS:
            raise ValueError(f"model 必须是以下值之一: {ALLOWED_MODELS}")
        return v


class StreamRequest(BaseModel):
    query: str
    model: str | None = None

    @field_validator("query")
    @classmethod
    def query_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("query 不能为空")
        return v.strip()

    @field_validator("model")
    @classmethod
    def model_must_be_allowed(cls, v):
        if v is None:
            return v
        if v not in ALLOWED_MODELS:
            raise ValueError(f"model 必须是以下值之一: {ALLOWED_MODELS}")
        return v


def _sse_event(event_type: str, **kwargs) -> str:
    payload = {"type": event_type, **kwargs}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.exception_handler(RAGBaseException)
async def rag_exception_handler(request: Request, exc: RAGBaseException):
    logger.error(f"[{exc.code}] {exc.message}" + (f" - {exc.detail}" if exc.detail else ""))
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.to_dict()},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        field = ".".join(str(loc) for loc in err["loc"]) if err["loc"] else "body"
        errors.append(f"{field}: {err['msg']}")
    detail = "; ".join(errors) if errors else "请求参数无效"
    logger.warning(f"[VALIDATION_ERROR] {detail}")
    return JSONResponse(
        status_code=400,
        content={"error": {"code": "VALIDATION_ERROR", "message": "参数校验失败", "detail": detail}},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"[INTERNAL_ERROR] Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "服务内部错误"}},
    )


@app.get("/")
def index():
    return {"message": "RAG service running"}


@app.post("/chat")
def chat(request: QueryRequest, req: Request):
    session_id = get_session_id(req)
    set_session_model(session_id, request.model)
    model = sessions[session_id]["model"]
    add_history(session_id, "user", request.query)
    answer, is_fallback = rag.query(request.query, model=model)
    add_history(session_id, "assistant", answer)
    response = {"query": request.query, "answer": answer, "session_id": session_id, "model": model}
    if is_fallback:
        response["is_fallback"] = True
    return response


@app.get("/chat/history")
def get_history(req: Request):
    session_id = req.headers.get("X-Session-Id")
    if not session_id or session_id not in sessions:
        return {"history": [], "session_id": session_id or str(uuid.uuid4()), "model": DEFAULT_MODEL}
    return {
        "history": sessions[session_id]["history"],
        "session_id": session_id,
        "model": sessions[session_id]["model"],
    }


@app.delete("/chat/history")
def clear_history(req: Request):
    session_id = req.headers.get("X-Session-Id")
    if session_id and session_id in sessions:
        sessions[session_id]["history"] = []
    return {"ok": True}


@app.post("/chat/stream")
async def chat_stream(request: StreamRequest, req: Request):
    session_id = get_session_id(req)
    set_session_model(session_id, request.model)
    model = sessions[session_id]["model"]
    add_history(session_id, "user", request.query)

    history = sessions[session_id]["history"][:-1]

    async def event_generator():
        full_answer = ""
        is_fallback = False
        try:
            yield _sse_event("session", session_id=session_id, model=model)

            stream_iter, is_fallback = rag.query_stream(request.query, history, model=model)

            for chunk in stream_iter:
                if chunk:
                    full_answer += chunk
                    yield _sse_event("text", content=chunk)

            add_history(session_id, "assistant", full_answer)

            if is_fallback:
                yield _sse_event("fallback", message="AI 服务异常，已返回兜底回复")

            yield _sse_event("done")

        except RAGBaseException as e:
            logger.error(f"[{e.code}] {e.message}" + (f" - {e.detail}" if e.detail else ""))
            yield _sse_event("error", code=e.code, message=e.message)
        except Exception as e:
            logger.exception(f"[INTERNAL_ERROR] stream error: {e}")
            yield _sse_event("error", code="INTERNAL_ERROR", message="服务内部错误")

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


# ==============================
# Agent Endpoints
# 独立于普通 RAG 聊天的 Agent 会话，使用独立的 session 命名空间
# 图结构：retrieve → agent ↔ tools（见 my_agent.py）
# ==============================

def _get_agent_session_id(request: Request) -> str:
    session_id = request.headers.get("X-Session-Id")
    if not session_id:
        session_id = str(uuid.uuid4())
    if session_id not in agent_sessions:
        agent_sessions[session_id] = {
            "model": DEFAULT_MODEL,
        }
    return session_id


def _set_agent_session_model(session_id: str, model: str | None):
    if model and model in ALLOWED_MODELS:
        agent_sessions[session_id]["model"] = model


class AgentQueryRequest(BaseModel):
    query: str
    model: str | None = None

    @field_validator("query")
    @classmethod
    def query_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("query 不能为空")
        return v.strip()

    @field_validator("model")
    @classmethod
    def model_must_be_allowed(cls, v):
        if v is None:
            return v
        if v not in ALLOWED_MODELS:
            raise ValueError(f"model 必须是以下值之一: {ALLOWED_MODELS}")
        return v


class AgentStreamRequest(BaseModel):
    query: str
    model: str | None = None

    @field_validator("query")
    @classmethod
    def query_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("query 不能为空")
        return v.strip()

    @field_validator("model")
    @classmethod
    def model_must_be_allowed(cls, v):
        if v is None:
            return v
        if v not in ALLOWED_MODELS:
            raise ValueError(f"model 必须是以下值之一: {ALLOWED_MODELS}")
        return v


@app.post("/agent/chat")
def agent_chat(request: AgentQueryRequest, req: Request):
    session_id = _get_agent_session_id(req)
    _set_agent_session_model(session_id, request.model)
    model = agent_sessions[session_id]["model"]

    answer, is_fallback = agent.chat(request.query, thread_id=session_id, model=model)

    history = agent.get_history(session_id)
    tool_calls = []
    for msg in reversed(history):
        if msg["role"] == "assistant" and msg.get("tool_calls"):
            tool_calls = msg["tool_calls"]
            break

    response = {
        "query": request.query,
        "answer": answer,
        "session_id": session_id,
        "model": model,
    }
    if tool_calls:
        response["tool_calls"] = tool_calls
    if is_fallback:
        response["is_fallback"] = True
    return response


@app.get("/agent/chat/history")
def get_agent_history(req: Request):
    session_id = req.headers.get("X-Session-Id")
    if not session_id or session_id not in agent_sessions:
        return {"history": [], "session_id": session_id or str(uuid.uuid4()), "model": DEFAULT_MODEL}
    history = agent.get_history(session_id)
    return {
        "history": history,
        "session_id": session_id,
        "model": agent_sessions[session_id]["model"],
    }


@app.delete("/agent/chat/history")
def clear_agent_history(req: Request):
    session_id = req.headers.get("X-Session-Id")
    if session_id and session_id in agent_sessions:
        agent.clear_history(session_id)
    return {"ok": True}


@app.post("/agent/chat/stream")
async def agent_chat_stream(request: AgentStreamRequest, req: Request):
    """Agent 流式对话（SSE）。

    事件类型与 /chat/stream 对齐，额外支持 tool_call / tool_result 事件。
    前端可选择忽略 tool 事件，渲染体验与普通聊天一致。
    """
    session_id = _get_agent_session_id(req)
    _set_agent_session_model(session_id, request.model)
    model = agent_sessions[session_id]["model"]

    async def event_generator():
        try:
            yield _sse_event("session", session_id=session_id, model=model)

            stream_iter = agent.chat_stream(request.query, thread_id=session_id, model=model)

            for event in stream_iter:
                event_type = event.get("type", "")
                if event_type == "text":
                    yield _sse_event("text", content=event["content"])
                elif event_type == "tool_call":
                    yield _sse_event("tool_call", name=event.get("name", ""), args=event.get("args", {}))
                elif event_type == "tool_result":
                    yield _sse_event("tool_result", name=event.get("name", ""), content=event.get("content", ""))
                elif event_type == "fallback":
                    yield _sse_event("fallback", message=event.get("message", ""))
                elif event_type == "error":
                    yield _sse_event("error", code=event.get("code", "AGENT_ERROR"), message=event.get("message", "Agent 执行异常"))
                elif event_type == "done":
                    yield _sse_event("done")

        except Exception as e:
            logger.exception(f"[AGENT_ERROR] stream error: {e}")
            yield _sse_event("error", code="INTERNAL_ERROR", message="服务内部错误")

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
