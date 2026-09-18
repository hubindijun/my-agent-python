"""
LLM 调用的重试与降级工具。

- with_llm_retry / with_llm_retry_stream：指数退避 + 抖动
  可重试错误：限流 / 超时 / 服务端 / 连接错误（鉴权错误不重试）
  max_attempts=None 时从配置自动读取（网关模式 1 次，直连模式 3 次）
- with_fallback / with_fallback_stream：捕获任意 LLMError，返回兜底文案
"""

import functools
import time
import random

from infra.exceptions import (
    LLMError,
    LLMAuthError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
    LLMConnectionError,
)

RETRYABLE_ERRORS = (LLMRateLimitError, LLMServerError, LLMTimeoutError, LLMConnectionError)

FALLBACK_MESSAGE = "抱歉，AI 服务暂时繁忙，请稍后再试。"


def _get_effective_attempts(max_attempts: int | None) -> int:
    """延迟读取配置中的重试次数，避免循环导入。"""
    if max_attempts is not None:
        return max_attempts
    try:
        from core.config import get_settings
        return get_settings().effective_retry_attempts
    except Exception:
        return 3  # 安全兜底


def with_llm_retry(max_attempts=None, initial_wait=1.0, backoff=2.0, jitter=0.1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempts = _get_effective_attempts(max_attempts)
            wait = initial_wait
            last_exc = None
            for attempt in range(attempts):
                try:
                    return func(*args, **kwargs)
                except RETRYABLE_ERRORS as e:
                    last_exc = e
                    if attempt == attempts - 1:
                        break
                    sleep_time = wait * (1 + random.uniform(-jitter, jitter))
                    time.sleep(max(0, sleep_time))
                    wait *= backoff
                except LLMAuthError:
                    raise
            raise last_exc
        return wrapper
    return decorator


def with_llm_retry_stream(max_attempts=None, initial_wait=1.0, backoff=2.0, jitter=0.1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempts = _get_effective_attempts(max_attempts)
            wait = initial_wait
            last_exc = None
            for attempt in range(attempts):
                try:
                    chunks = list(func(*args, **kwargs))
                    return iter(chunks)
                except RETRYABLE_ERRORS as e:
                    last_exc = e
                    if attempt == attempts - 1:
                        break
                    sleep_time = wait * (1 + random.uniform(-jitter, jitter))
                    time.sleep(max(0, sleep_time))
                    wait *= backoff
                except LLMAuthError:
                    raise
            raise last_exc
        return wrapper
    return decorator


def with_fallback(primary_fn, fallback_message=FALLBACK_MESSAGE):
    try:
        result = primary_fn()
        return result, False
    except LLMError:
        return fallback_message, True


def with_fallback_stream(primary_fn, fallback_message=FALLBACK_MESSAGE):
    try:
        chunks = list(primary_fn())
        return iter(chunks), False
    except LLMError:
        return iter([fallback_message]), True
