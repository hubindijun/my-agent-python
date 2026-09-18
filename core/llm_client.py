"""
统一 LLM 客户端。

封装 ChatOpenAI 的创建、缓存、错误映射。
MyChat 和 MyAgent 都通过 LLMClient 获取 LLM 实例，消除重复代码。

- 单例模式：LLMClient.get_instance()
- 按模型名缓存 ChatOpenAI 实例
- 错误映射集中在 map_error()
- 自动从 Settings 获取 base_url / api_key
"""

import logging

from langchain_openai import ChatOpenAI

from core.config import get_settings
from infra.exceptions import (
    LLMError,
    LLMAuthError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
    LLMConnectionError,
)

logger = logging.getLogger(__name__)


class LLMClient:
    _instance: "LLMClient | None" = None

    def __init__(self):
        self.settings = get_settings()
        self._llm_cache: dict[str, ChatOpenAI] = {}

    @classmethod
    def get_instance(cls) -> "LLMClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def default_model(self) -> str:
        return self.settings.openai_model

    def get_llm(self, model: str | None = None) -> ChatOpenAI:
        """按模型名获取 ChatOpenAI 实例，懒加载并缓存。"""
        model_name = model or self.default_model
        if model_name not in self._llm_cache:
            try:
                self._llm_cache[model_name] = ChatOpenAI(
                    model=model_name,
                    api_key=self.settings.effective_api_key,
                    base_url=self.settings.effective_base_url,
                    streaming=True,
                )
            except Exception as e:
                raise LLMError(
                    message=f"LLM 客户端初始化失败 ({model_name})",
                    detail=str(e),
                ) from e
        return self._llm_cache[model_name]

    @staticmethod
    def map_error(e: Exception) -> LLMError:
        """将 OpenAI SDK 原始异常映射为项目自定义 LLMError 子类。"""
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
