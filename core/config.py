"""
集中配置管理。

使用 pydantic-settings 从 .env 读取所有配置，
替代散落的 os.getenv() / load_dotenv()。

通过 get_settings() 获取单例。
"""

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _env_int(name: str, default: int | None = None) -> int | None:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except (ValueError, TypeError):
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name, "").lower()
    if v in ("true", "1", "yes", "on"):
        return True
    if v in ("false", "0", "no", "off", ""):
        return default if v == "" else False
    return default


def _env_list(name: str, default: list[str] | None = None) -> list[str]:
    if default is None:
        default = []
    v = os.getenv(name)
    if v is None or v == "":
        return list(default)
    return [m.strip() for m in v.split(",") if m.strip()]


class Settings:
    """应用配置，从环境变量读取。"""

    def __init__(self):
        # ---- 直连模式 LLM ----
        self.openai_api_key = _env_str("OPENAI_API_KEY")
        self.openai_api_base = _env_str("OPENAI_API_BASE")
        self.openai_model = _env_str("OPENAI_MODEL")

        # ---- LiteLLM 网关 ----
        self.litellm_enabled = _env_bool("LITELLM_ENABLED", False)
        self.litellm_proxy_url = _env_str("LITELLM_PROXY_URL", "http://localhost:4000/v1")
        self.litellm_api_key = _env_str("LITELLM_API_KEY")

        # ---- 应用层重试 ----
        # None = 自动：网关模式 1 次，直连模式 3 次
        self.llm_retry_attempts = _env_int("LLM_RETRY_ATTEMPTS")

        # ---- 直连模式模型白名单 ----
        # .env 中用逗号分隔，如: ALLOWED_MODELS=model-a,model-b
        self.allowed_models = _env_list(
            "ALLOWED_MODELS",
            ["deepseek-v4-flash", "deepseek-v4-pro"],
        )

    @property
    def effective_base_url(self) -> str:
        """根据模式返回实际 base_url。"""
        if self.litellm_enabled:
            return self.litellm_proxy_url
        return self.openai_api_base

    @property
    def effective_api_key(self) -> str:
        if self.litellm_enabled:
            return self.litellm_api_key
        return self.openai_api_key

    @property
    def effective_retry_attempts(self) -> int:
        if self.llm_retry_attempts is not None:
            return self.llm_retry_attempts
        return 1 if self.litellm_enabled else 3

    def validate(self) -> None:
        """启动时校验配置完整性。"""
        if self.litellm_enabled:
            if not self.litellm_api_key:
                raise ValueError("LITELLM_ENABLED=true 时必须配置 LITELLM_API_KEY")
            if not self.litellm_proxy_url:
                raise ValueError("LITELLM_ENABLED=true 时必须配置 LITELLM_PROXY_URL")
        else:
            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY 未配置")
            if not self.openai_api_base:
                raise ValueError("OPENAI_API_BASE 未配置")
            if not self.openai_model:
                raise ValueError("OPENAI_MODEL 未配置")

    @property
    def effective_base_url(self) -> str:
        """根据模式返回实际 base_url。"""
        if self.litellm_enabled:
            return self.litellm_proxy_url
        return self.openai_api_base

    @property
    def effective_api_key(self) -> str:
        if self.litellm_enabled:
            return self.litellm_api_key
        return self.openai_api_key

    @property
    def effective_retry_attempts(self) -> int:
        if self.llm_retry_attempts is not None:
            return self.llm_retry_attempts
        return 1 if self.litellm_enabled else 3

    def validate(self) -> None:
        """启动时校验配置完整性。"""
        if self.litellm_enabled:
            if not self.litellm_api_key:
                raise ValueError("LITELLM_ENABLED=true 时必须配置 LITELLM_API_KEY")
            if not self.litellm_proxy_url:
                raise ValueError("LITELLM_ENABLED=true 时必须配置 LITELLM_PROXY_URL")
        else:
            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY 未配置")
            if not self.openai_api_base:
                raise ValueError("OPENAI_API_BASE 未配置")
            if not self.openai_model:
                raise ValueError("OPENAI_MODEL 未配置")


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.validate()
    return s
