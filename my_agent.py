import logging
import os

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage, BaseMessage
from langchain_core.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from my_rag import MyRag
from exceptions import (
    LLMError,
    LLMAuthError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
    LLMConnectionError,
    RetrieverError,
    AgentError,
)
from retry_utils import with_llm_retry, FALLBACK_MESSAGE

logger = logging.getLogger(__name__)


class AgentState(MessagesState):
    context: str = ""
    is_fallback: bool = False


def _map_openai_error(e: Exception) -> LLMError:
    name = type(e).__name__
    msg = str(e)
    lowered = (name + msg).lower()
    if "auth" in lowered or "authentication" in lowered:
        return LLMAuthError(detail=msg)
    if "rate" in lowered or "ratelimit" in lowered or "rate_limit" in lowered:
        return LLMRateLimitError(detail=msg)
    if "timeout" in lowered:
        return LLMTimeoutError(detail=msg)
    if "connection" in lowered or "api_connection" in lowered:
        return LLMConnectionError(detail=msg)
    if "apierror" in lowered or "serviceunavailable" in lowered or "internalservererror" in lowered:
        return LLMServerError(detail=msg)
    return LLMError(detail=msg)


class MyAgent:
    def __init__(self, rag: MyRag, extra_tools: list[BaseTool] | None = None):
        self.rag = rag

        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_API_BASE")
        default_model = os.getenv("OPENAI_MODEL")
        if not api_key or not base_url or not default_model:
            raise LLMError(message="Agent LLM 配置缺失，请检查 OPENAI_API_KEY / OPENAI_API_BASE / OPENAI_MODEL")

        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model
        self._llm_cache: dict[str, ChatOpenAI] = {}

        self.tools: list[BaseTool] = list(extra_tools) if extra_tools else []

        self.system_prompt = (
            "你是一个专业的AI助手。请根据提供的上下文回答用户问题。"
            "如果上下文中没有相关信息，请基于你的知识礼貌回答。\n\n"
            "回答要求：\n"
            "1. 使用清晰的段落组织内容\n"
            "2. 适当使用列表展示要点\n"
            "3. 关键信息可以加粗\n"
            "4. 保持结构清晰，易于阅读\n\n"
            "Context:\n{context}"
        )

        self.memory = MemorySaver()
        self.graph = self._build_graph()

    def _get_llm(self, model: str | None = None) -> ChatOpenAI:
        model_name = model or self.default_model
        if model_name not in self._llm_cache:
            try:
                self._llm_cache[model_name] = ChatOpenAI(
                    model=model_name,
                    api_key=self.api_key,
                    base_url=self.base_url,
                    streaming=True,
                )
            except Exception as e:
                raise LLMError(message=f"Agent LLM 初始化失败: {model_name}", detail=str(e)) from e
        return self._llm_cache[model_name]

    def _build_graph(self):
        builder = StateGraph(AgentState)

        builder.add_node("retrieve", self._retrieve_node)
        builder.add_node("agent", self._agent_node)
        builder.add_node("tools", ToolNode(self.tools))

        builder.add_edge(START, "retrieve")
        builder.add_edge("retrieve", "agent")
        builder.add_conditional_edges("agent", self._should_continue, {
            "tools": "tools",
            "end": END,
        })
        builder.add_edge("tools", "agent")

        return builder.compile(checkpointer=self.memory)

    def _retrieve_node(self, state: AgentState) -> dict:
        messages = state["messages"]
        query = messages[-1].content if messages else ""
        try:
            context = self.rag._retrieve(query)
        except RetrieverError as e:
            logger.warning(f"Agent RAG 检索失败: {e.message}")
            context = ""
        return {"context": context}

    def _agent_node(self, state: AgentState) -> dict:
        context = state.get("context", "")
        messages = state["messages"]

        system_text = self.system_prompt.format(context=context if context else "（暂无上下文）")

        full_messages = [SystemMessage(content=system_text)] + list(messages)

        llm = self._get_llm()
        if self.tools:
            llm = llm.bind_tools(self.tools)

        def _invoke_with_error_mapping():
            try:
                return llm.invoke(full_messages)
            except Exception as e:
                raise _map_openai_error(e) from e

        try:
            @with_llm_retry()
            def _call():
                return _invoke_with_error_mapping()

            response = _call()
            return {"messages": [response], "is_fallback": False}
        except LLMError:
            fallback_msg = AIMessage(content=FALLBACK_MESSAGE)
            return {"messages": [fallback_msg], "is_fallback": True}

    def _should_continue(self, state: AgentState) -> str:
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return "end"

    def chat(self, query: str, thread_id: str, model: str | None = None) -> tuple[str, bool]:
        config = {"configurable": {"thread_id": thread_id}}
        try:
            result = self.graph.invoke(
                {"messages": [HumanMessage(content=query)]},
                config=config,
            )
        except Exception as e:
            raise AgentError(message="Agent 执行失败", detail=str(e)) from e

        is_fallback = result.get("is_fallback", False)
        last_msg = result["messages"][-1]
        answer = last_msg.content if isinstance(last_msg.content, str) else ""
        return answer, is_fallback

    def chat_stream(self, query: str, thread_id: str, model: str | None = None):
        config = {"configurable": {"thread_id": thread_id}}

        def event_generator():
            try:
                is_fallback = False
                for event in self.graph.stream(
                    {"messages": [HumanMessage(content=query)]},
                    config=config,
                    stream_mode="values",
                ):
                    messages = event.get("messages", [])
                    if not messages:
                        continue
                    last_msg = messages[-1]

                    if isinstance(last_msg, ToolMessage):
                        yield {"type": "tool_result", "name": last_msg.name, "content": last_msg.content}
                    elif isinstance(last_msg, AIMessage):
                        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                            for tc in last_msg.tool_calls:
                                yield {"type": "tool_call", "name": tc.get("name", ""), "args": tc.get("args", {})}
                        else:
                            content = last_msg.content if isinstance(last_msg.content, str) else ""
                            if content:
                                yield {"type": "text", "content": content}
                                is_fallback = event.get("is_fallback", False)

                if is_fallback:
                    yield {"type": "fallback", "message": "AI 服务异常，已返回兜底回复"}
                yield {"type": "done"}

            except Exception as e:
                if isinstance(e, AgentError):
                    yield {"type": "error", "code": e.code, "message": e.message}
                else:
                    logger.exception(f"Agent stream error: {e}")
                    yield {"type": "error", "code": "AGENT_ERROR", "message": "Agent 执行异常"}

        return event_generator()

    def get_history(self, thread_id: str) -> list[dict]:
        config = {"configurable": {"thread_id": thread_id}}
        state = self.graph.get_state(config)
        if not state or not state.values.get("messages"):
            return []

        result = []
        for msg in state.values["messages"]:
            if isinstance(msg, HumanMessage):
                result.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                entry = {"role": "assistant", "content": msg.content if isinstance(msg.content, str) else ""}
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    entry["tool_calls"] = [
                        {"name": tc.get("name", ""), "args": tc.get("args", {})}
                        for tc in msg.tool_calls
                    ]
                result.append(entry)
            elif isinstance(msg, ToolMessage):
                result.append({"role": "tool", "name": msg.name, "content": msg.content})
        return result

    def clear_history(self, thread_id: str) -> None:
        try:
            self.memory.delete_thread(thread_id)
        except Exception:
            pass
