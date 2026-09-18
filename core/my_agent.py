"""
LangGraph Agent — 基于 LangGraph 的智能体，内置 RAG 检索节点 + ReAct 工具循环。

图结构：
    START → retrieve (RAG检索) → agent (LLM+tools) ↔ tools → END

设计要点：
- LLM 实例通过 LLMClient 获取，与 MyChat 共享配置与缓存
- 只复用公共工具层：retry_utils（重试降级）、exceptions（异常体系）
- MyRag 仅用于检索（只读调用 _retrieve），不修改其内部实现
"""

import logging

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from core.my_rag import MyRag
from core.llm_client import LLMClient
from infra.exceptions import (
    LLMError,
    RetrieverError,
    AgentError,
)
from infra.retry_utils import with_llm_retry, FALLBACK_MESSAGE

logger = logging.getLogger(__name__)


MAX_TOOL_RETRIES = 2


class AgentState(MessagesState):
    """Agent 图状态定义。

    Attributes:
        messages: 会话消息列表（继承自 MessagesState，含 Human/AIMessage/ToolMessage）
        context: RAG 检索到的上下文文本，由 retrieve 节点写入
        is_fallback: 本次响应是否为降级兜底回复
        tool_error_count: 当前轮次工具调用错误次数，达到 MAX_TOOL_RETRIES 后强制结束
        max_retries_reached: 工具错误重试次数是否已达上限
    """
    context: str = ""
    is_fallback: bool = False
    tool_error_count: int = 0
    max_retries_reached: bool = False


class MyAgent:
    def __init__(self, rag: MyRag, extra_tools: list[BaseTool] | None = None, llm_client: LLMClient | None = None):
        self.rag = rag
        self.llm_client = llm_client or LLMClient.get_instance()
        self.default_model = self.llm_client.default_model

        self.tools: list[BaseTool] = list(extra_tools) if extra_tools else []

        self.system_prompt = (
            "你是一个简洁高效的AI助手。请根据提供的上下文回答用户问题。"
            "如果上下文中没有相关信息，请基于你的知识礼貌回答。\n\n"
            "回答原则：\n"
            "1. 回答尽量简洁，直接给出答案，不要多余的客套和铺垫\n"
            "2. 不要使用 markdown 格式（加粗、斜体、列表等），用纯文本回答\n"
            "3. 涉及加减乘除等数学计算时，必须使用 calculator 工具，不要心算\n"
            "4. 调用 calculator 工具得到结果后，直接输出最终数值，"
            "不要重复算式、不要写计算过程、不要加任何前缀或解释\n"
            "5. 如果工具调用失败，请修正参数后重试，"
            f"同一轮最多重试 {MAX_TOOL_RETRIES} 次；多次失败则向用户说明问题\n\n"
            "示例：\n"
            "用户：123 + 456 等于多少？\n"
            "（调用 calculator 工具，表达式 \"123 + 456\"，得到结果 579）\n"
            "助手：579\n\n"
            "Context:\n{context}"
        )

        self.memory = MemorySaver()
        self.graph = self._build_graph()

    def _get_llm(self, model: str | None = None):
        """按模型名获取 ChatOpenAI 实例。"""
        return self.llm_client.get_llm(model)

    def _build_graph(self):
        """构建 LangGraph StateGraph。

        流程：START → retrieve（RAG 检索）→ agent（LLM 决策）
                          ↑                        │
                          └────── tools ←──────────┘（有 tool_calls 时循环）

        MemorySaver 作为 checkpointer，支持多轮会话持久化。
        """
        builder = StateGraph(AgentState)

        self._tool_node = ToolNode(self.tools)

        builder.add_node("retrieve", self._retrieve_node)
        builder.add_node("agent", self._agent_node)
        builder.add_node("tools", self._tools_node)

        builder.add_edge(START, "retrieve")
        builder.add_edge("retrieve", "agent")
        builder.add_conditional_edges("agent", self._should_continue, {
            "tools": "tools",
            "end": END,
        })
        builder.add_edge("tools", "agent")

        return builder.compile(checkpointer=self.memory)

    def _retrieve_node(self, state: AgentState) -> dict:
        """RAG 检索节点：取最新用户消息作为 query，调用 MyRag 检索上下文。

        检索失败时降级为空上下文，不中断图执行（Agent 可基于纯 LLM 回答）。
        """
        messages = state["messages"]
        query = messages[-1].content if messages else ""
        try:
            context = self.rag._retrieve(query)
        except RetrieverError as e:
            logger.warning(f"Agent RAG 检索失败: {e.message}")
            context = ""
        return {"context": context}

    def _tools_node(self, state: AgentState) -> dict:
        """工具执行节点：调用 ToolNode 执行工具，并追踪工具错误次数。

        工具抛出异常时，LangChain ToolNode 会将 ToolMessage 标记为 is_error=True，
        以此判断是否计入错误计数；达到 MAX_TOOL_RETRIES 次后标记 max_retries_reached，
        _should_continue 会强制结束循环。
        """
        result = self._tool_node.invoke(state)
        tool_messages = result.get("messages", [])
        error_count = state.get("tool_error_count", 0)

        for msg in tool_messages:
            if getattr(msg, "is_error", False):
                error_count += 1

        update = {"messages": tool_messages, "tool_error_count": error_count}
        if error_count >= MAX_TOOL_RETRIES:
            update["max_retries_reached"] = True
        return update

    def _agent_node(self, state: AgentState) -> dict:
        """Agent 节点：LLM + tools binding，决定直接回答还是调用工具。

        LLM 调用外层套 with_llm_retry，
        重试耗尽后返回 fallback 消息，图正常结束。
        """
        context = state.get("context", "")
        messages = state["messages"]
        model = state.get("model")  # 从 state 中读取 model（由 chat/chat_stream 传入）

        system_text = self.system_prompt.format(context=context if context else "（暂无上下文）")

        full_messages = [SystemMessage(content=system_text)] + list(messages)

        llm = self._get_llm(model)
        if self.tools:
            llm = llm.bind_tools(self.tools)

        def _invoke_with_error_mapping():
            try:
                return llm.invoke(full_messages)
            except Exception as e:
                raise LLMClient.map_error(e) from e

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
        if state.get("max_retries_reached", False):
            return "end"
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return "end"

    def chat(self, query: str, thread_id: str, model: str | None = None, extra_config: dict | None = None) -> tuple[str, bool]:
        config: dict = {"configurable": {"thread_id": thread_id}}
        if extra_config:
            config.update(extra_config)
        try:
            result = self.graph.invoke(
                {"messages": [HumanMessage(content=query)], "model": model or self.default_model},
                config=config,
            )
        except Exception as e:
            raise AgentError(message="Agent 执行失败", detail=str(e)) from e

        is_fallback = result.get("is_fallback", False)
        last_msg = result["messages"][-1]
        answer = last_msg.content if isinstance(last_msg.content, str) else ""
        return answer, is_fallback

    def chat_stream(self, query: str, thread_id: str, model: str | None = None, extra_config: dict | None = None):
        """流式对话，生成结构化事件供 SSE 使用。

        事件类型：tool_result / tool_call / text / fallback / error / done
        使用 stream_mode="values" 监听 state 变化，从最新消息判断事件类型。
        """
        config: dict = {"configurable": {"thread_id": thread_id}}
        if extra_config:
            config.update(extra_config)

        def event_generator():
            try:
                is_fallback = False
                for event in self.graph.stream(
                    {"messages": [HumanMessage(content=query)], "model": model or self.default_model},
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
