#!/usr/bin/env python
import os
import logging

from dotenv import load_dotenv

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage

from exceptions import (
    LLMError,
    LLMAuthError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
    LLMConnectionError,
)
from retry_utils import with_llm_retry, with_llm_retry_stream

load_dotenv()

logger = logging.getLogger(__name__)


class MyChat:

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        default_model = os.getenv("OPENAI_MODEL")
        base_url = os.getenv("OPENAI_API_BASE")

        if not api_key:
            raise LLMError("OPENAI_API_KEY 环境变量未配置")
        if not default_model:
            raise LLMError("OPENAI_MODEL 环境变量未配置")
        if not base_url:
            raise LLMError("OPENAI_API_BASE 环境变量未配置")

        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model
        self._llm_cache: dict[str, ChatOpenAI] = {}

        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "你是一个AI助手。请根据用户提供的问题回答。"),
                ("human", "{query}"),
            ]
        )

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
                raise LLMError(f"LLM 客户端初始化失败 ({model_name}): {e}") from e
        return self._llm_cache[model_name]

    @staticmethod
    def _wrap_llm_error(func):
        try:
            return func()
        except Exception as e:
            raise _map_openai_error(e) from e

    @with_llm_retry()
    def chat(self, query: str, model: str | None = None) -> str:
        llm = self._get_llm(model)
        chain = self.prompt | llm | StrOutputParser()
        return self._wrap_llm_error(lambda: chain.invoke({"query": query}))

    @with_llm_retry()
    def rag_chat(self, query: str, context: str, model: str | None = None) -> str:
        llm = self._get_llm(model)
        rag_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "请根据下面上下文回答问题。\n"
                    "使用 Markdown 格式输出，合理分段并使用列表、加粗等让结构清晰。\n\n"
                    "Context:\n{context}",
                ),
                ("human", "{query}"),
            ]
        )
        chain = rag_prompt | llm | StrOutputParser()
        return self._wrap_llm_error(lambda: chain.invoke({"query": query, "context": context}))

    @with_llm_retry_stream()
    def rag_chat_stream(self, query: str, context: str, history: list = None, model: str | None = None):
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
                    "1. 使用 Markdown 格式输出，合理分段（段落之间用空行分隔）\n"
                    "2. 要点较多时使用有序或无序列表\n"
                    "3. 关键概念可以适当加粗强调\n"
                    "4. 结构清晰，层次分明，避免大段连续文字\n\n"
                    "Context:\n{context}",
                ),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{query}"),
            ]
        )

        chain = rag_prompt | llm | StrOutputParser()

        def _stream():
            try:
                for chunk in chain.stream({"query": query, "context": context, "history": history_messages}):
                    yield chunk
            except Exception as e:
                raise _map_openai_error(e) from e

        return _stream()


def _map_openai_error(e: Exception) -> LLMError:
    err_name = type(e).__name__

    if "Authentication" in err_name or "Auth" in err_name:
        return LLMAuthError(detail=str(e))
    if "RateLimit" in err_name or "rate_limit" in str(e).lower():
        return LLMRateLimitError(detail=str(e))
    if "Timeout" in err_name or "timeout" in str(e).lower():
        return LLMTimeoutError(detail=str(e))
    if "Connection" in err_name or "APIConnection" in err_name:
        return LLMConnectionError(detail=str(e))
    if "APIError" in err_name or "ServiceUnavailable" in err_name or "InternalServerError" in err_name:
        return LLMServerError(detail=str(e))

    return LLMError(message=f"LLM 调用失败: {err_name}", detail=str(e))
