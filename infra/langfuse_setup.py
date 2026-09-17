"""Langfuse 监控集成工具（适配 langfuse v4）。

Langfuse v4 的 CallbackHandler 从环境变量自动读取配置：
  LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST

使用方式：
  handler = get_langfuse_handler(session_id="xxx", trace_name="rag_chat")
  callbacks = [handler] if handler else None
  chain.invoke(..., config={"callbacks": callbacks, "metadata": build_langchain_metadata(...)})

创建失败时静默返回 None，保证主流程不受 Langfuse 不可用的影响。
"""

import os
import logging
import uuid

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

_langfuse_available = None


def _is_langfuse_available() -> bool:
    global _langfuse_available
    if _langfuse_available is not None:
        return _langfuse_available
    try:
        from langfuse.langchain import CallbackHandler  # noqa: F401
        _langfuse_available = True
    except ImportError:
        _langfuse_available = False
        logger.warning("langfuse 未安装，跳过监控上报")
    return _langfuse_available


def _check_env() -> bool:
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST")
    if not public_key or not secret_key or not host:
        logger.debug("LANGFUSE_* 环境变量不完整，跳过监控上报")
        return False
    return True


def _session_to_trace_id(session_id: str) -> str:
    """将任意 session_id 转换为 32 位 hex 的合法 Langfuse trace_id。

    对同一个 session_id 输出是确定性的（基于 UUID5），
    这样同一会话内多次请求可以通过 session_id 关联。
    """
    ns = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    return str(uuid.uuid5(ns, session_id)).replace("-", "")


def get_langfuse_handler(
    session_id: str | None = None,
    user_id: str | None = None,
    metadata: dict | None = None,
    trace_name: str | None = None,
):
    """创建 Langfuse CallbackHandler 实例。

    Langfuse v4 自动从环境变量读取密钥和 host。
    trace_context 用于设置自定义 trace_id（必须是 32 位 hex）。
    session_id / trace_name 等通过 LangChain metadata 传递。

    如果环境变量未配置或 SDK 不可用，返回 None，调用方应兼容 None。
    """
    if not _is_langfuse_available():
        return None

    if not _check_env():
        return None

    try:
        from langfuse.langchain import CallbackHandler

        # 每次请求一个独立的 trace
        trace_id = str(uuid.uuid4()).replace("-", "")
        handler = CallbackHandler(
            trace_context={"trace_id": trace_id}
        )
        return handler
    except Exception as e:
        logger.warning(f"Langfuse handler 创建失败，跳过监控: {e}")
        return None


def build_langchain_metadata(
    session_id: str | None = None,
    user_id: str | None = None,
    trace_name: str | None = None,
    extra: dict | None = None,
) -> dict:
    """构建 LangChain config 中的 metadata，供 Langfuse 采集。

    Langfuse v4 从 LangChain RunnableConfig 的 metadata 中读取
    特定字段映射到 trace 属性：
      - langfuse_trace.name → trace name
      - langfuse_trace.session_id → session id
      - langfuse_trace.user_id → user id
      - langfuse_trace.tags → tags
      - langfuse_trace.metadata → 自定义 metadata
    """
    trace_meta = {}
    if trace_name:
        trace_meta["name"] = trace_name
    if session_id:
        trace_meta["session_id"] = session_id
    if user_id:
        trace_meta["user_id"] = user_id

    result = extra or {}
    if trace_meta:
        result["langfuse_trace"] = trace_meta
    return result


def flush_langfuse():
    """强制 flush 所有待上报的事件。"""
    if not _is_langfuse_available():
        return
    try:
        from langfuse import Langfuse
        Langfuse().flush()
    except Exception as e:
        logger.debug(f"Langfuse flush 失败: {e}")
