import functools
import time
import random

from exceptions import (
    LLMError,
    LLMAuthError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
    LLMConnectionError,
)

RETRYABLE_ERRORS = (LLMRateLimitError, LLMServerError, LLMTimeoutError, LLMConnectionError)

FALLBACK_MESSAGE = "抱歉，AI 服务暂时繁忙，请稍后再试。"


def with_llm_retry(max_attempts=3, initial_wait=1.0, backoff=2.0, jitter=0.1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            wait = initial_wait
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except RETRYABLE_ERRORS as e:
                    last_exc = e
                    if attempt == max_attempts - 1:
                        break
                    sleep_time = wait * (1 + random.uniform(-jitter, jitter))
                    time.sleep(max(0, sleep_time))
                    wait *= backoff
                except LLMAuthError:
                    raise
            raise last_exc
        return wrapper
    return decorator


def with_llm_retry_stream(max_attempts=3, initial_wait=1.0, backoff=2.0, jitter=0.1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            wait = initial_wait
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    chunks = list(func(*args, **kwargs))
                    return iter(chunks)
                except RETRYABLE_ERRORS as e:
                    last_exc = e
                    if attempt == max_attempts - 1:
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
