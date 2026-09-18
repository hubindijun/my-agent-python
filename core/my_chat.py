"""
MyChat — LLM 聊天封装。

负责 RAG prompt 构建、LLM 调用编排。
LLM 实例创建、缓存、错误映射统一委托给 LLMClient。
所有 LLM 调用通过 retry_utils 的装饰器实现指数退避重试。
"""

import logging

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage

from core.llm_client import LLMClient
from infra.retry_utils import with_llm_retry, with_llm_retry_stream

logger = logging.getLogger(__name__)


class MyChat:

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm_client = llm_client or LLMClient.get_instance()
        self.default_model = self.llm_client.default_model

        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "你是一个AI助手。请根据用户提供的问题回答。"),
                ("human", "{query}"),
            ]
        )

    def _get_llm(self, model: str | None = None):
        """按模型名获取 ChatOpenAI 实例。"""
        return self.llm_client.get_llm(model)

    @staticmethod
    def _wrap_llm_error(func):
        try:
            return func()
        except Exception as e:
            raise LLMClient.map_error(e) from e

    @with_llm_retry()
    def chat(self, query: str, model: str | None = None, config: dict | None = None) -> str:
        llm = self._get_llm(model)
        chain = self.prompt | llm | StrOutputParser()
        return self._wrap_llm_error(lambda: chain.invoke({"query": query}, config=config))

    @with_llm_retry()
    def rag_chat(self, query: str, context: str, model: str | None = None, config: dict | None = None) -> str:
        """RAG 问答（非流式）。根据检索到的上下文回答问题。"""
        llm = self._get_llm(model)
        rag_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "请根据下面上下文回答问题。\n"
                    "回答简洁直接，给出明确答案，不要使用 Markdown 加粗、斜体等格式。\n\n"
                    "Context:\n{context}",
                ),
                ("human", "{query}"),
            ]
        )
        chain = rag_prompt | llm | StrOutputParser()
        return self._wrap_llm_error(lambda: chain.invoke({"query": query, "context": context}, config=config))

    @with_llm_retry_stream()
    def rag_chat_stream(self, query: str, context: str, history: list = None, model: str | None = None, config: dict | None = None):
        """RAG 问答（流式）。支持传入会话历史，用于多轮对话。"""
        if history is None:
            history = []

        llm = self._get_llm(model)

        history_messages = []
        for msg in history:
            if msg["role"] == "user":
                history_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                history_messages.append(AIMessage(content=msg["content"]))

        rag_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个专业的AI助手，请根据提供的上下文回答用户问题。"
                    "如果上下文中没有相关信息，请基于你的知识礼貌回答。\n\n"
                    "回答要求：\n"
                    "1. 回答简洁直接，给出明确答案，不要多余的客套和铺垫\n"
                    "2. 要点较多时使用有序或无序列表\n"
                    "3. 不要使用 Markdown 加粗、斜体等格式，用纯文本回答\n"
                    "4. 结构清晰，避免大段连续文字\n\n"
                    "Context:\n{context}",
                ),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{query}"),
            ]
        )

        chain = rag_prompt | llm | StrOutputParser()

        def _stream():
            try:
                for chunk in chain.stream({"query": query, "context": context, "history": history_messages}, config=config):
                    yield chunk
            except Exception as e:
                raise LLMClient.map_error(e) from e

        return _stream()
