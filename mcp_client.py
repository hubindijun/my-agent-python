"""
MCP 客户端封装 — 将 MCP over SSE 服务的工具桥接到 LangChain Agent。

设计原则（参考 langfuse_setup.py）：
- 优雅降级：SDK 未安装 / 配置缺失 / 连接失败时，返回空工具列表，不影响主流程
- 与现有工具体系一致：MCP 工具转为标准 BaseTool，通过 extra_tools 注入 MyAgent
- 工具调用时按需建立 SSE 连接（每次调用独立连接，天然支持重连）
"""

import asyncio
import logging
import os
from typing import Any

from dotenv import load_dotenv
from langchain_core.tools import BaseTool

load_dotenv()

logger = logging.getLogger(__name__)

# 已配置的 MCP 服务列表（大写，与环境变量前缀对应）
# 未来添加新服务：在此列表中追加服务名，并在 .env 中添加 MCP_<NAME>_URL 等配置
_SERVICES = ["SPRINGBOOT"]

_mcp_available: bool | None = None


def _is_mcp_available() -> bool:
    """检测 langchain-mcp-adapters SDK 是否已安装。

    懒检测，结果缓存到模块级变量 _mcp_available。
    """
    global _mcp_available
    if _mcp_available is not None:
        return _mcp_available
    try:
        from langchain_mcp_adapters.tools import load_mcp_tools  # noqa: F401
        _mcp_available = True
    except ImportError as e:
        logger.warning(f"MCP SDK 未安装 (langchain-mcp-adapters): {e}")
        _mcp_available = False
    except Exception as e:
        logger.warning(f"MCP SDK 导入失败: {e}")
        _mcp_available = False
    return _mcp_available


def _check_global_enabled() -> bool:
    """检查 MCP_ENABLED 全局开关。"""
    return os.getenv("MCP_ENABLED", "true").lower() in ("true", "1", "yes", "on")


def _get_service_config(service_name: str) -> dict[str, Any] | None:
    """读取单个 MCP 服务的配置。

    环境变量命名约定：MCP_<SERVICE_NAME>_URL / _TIMEOUT / _API_KEY

    返回：
        包含 url / timeout / api_key 的字典；URL 为空时返回 None。
    """
    prefix = f"MCP_{service_name}_"
    url = os.getenv(f"{prefix}URL", "").strip()
    if not url:
        logger.debug(f"MCP 服务 {service_name} 未配置 URL，跳过")
        return None

    timeout_str = os.getenv(f"{prefix}TIMEOUT", "10").strip()
    try:
        timeout = float(timeout_str)
    except ValueError:
        logger.warning(f"MCP 服务 {service_name} 的 TIMEOUT 无效 ({timeout_str})，使用默认 10s")
        timeout = 10.0

    api_key = os.getenv(f"{prefix}API_KEY", "").strip()

    return {"url": url, "timeout": timeout, "api_key": api_key}


def _build_sse_connection(url: str, timeout: float, api_key: str | None) -> dict[str, Any]:
    """构建 SSE 连接配置字典（langchain-mcp-adapters 的 SSEConnection 格式）。"""
    headers: dict[str, str] = {}
    if api_key:
        headers["X-API-Key"] = api_key

    return {
        "transport": "sse",
        "url": url,
        "timeout": timeout,
        "headers": headers if headers else None,
    }


def load_mcp_tools_for_service(service_name: str) -> list[BaseTool]:
    """加载单个 MCP 服务的工具列表。

    完整降级链路（任一环节失败均返回空列表，不抛异常）：
        全局开关关闭 → []
        SDK 未安装  → []
        配置缺失    → []
        连接失败    → []
        工具拉取失败 → []

    Args:
        service_name: 服务名（大写，对应环境变量前缀 MCP_<NAME>_）

    Returns:
        转换后的 LangChain BaseTool 列表；失败时返回空列表。
    """
    if not _check_global_enabled():
        logger.debug("MCP 全局开关已关闭，跳过工具加载")
        return []

    if not _is_mcp_available():
        return []

    config = _get_service_config(service_name)
    if not config:
        return []

    url = config["url"]
    timeout = config["timeout"]
    api_key = config["api_key"] or None

    connection = _build_sse_connection(url, timeout, api_key)

    try:
        from langchain_mcp_adapters.tools import load_mcp_tools

        tools = asyncio.run(_async_load_tools(load_mcp_tools, connection, service_name))
        logger.info(f"MCP 服务 {service_name} 加载成功，共 {len(tools)} 个工具: "
                    f"{[t.name for t in tools]}")
        return tools
    except Exception as e:
        logger.warning(f"MCP 服务 {service_name} 连接或工具加载失败: {e}，"
                       f"Agent 将仅使用本地工具")
        return []


async def _async_load_tools(load_fn, connection: dict, server_name: str) -> list[BaseTool]:
    """异步加载 MCP 工具（包装 asyncio.run 用）。"""
    return await load_fn(
        session=None,
        connection=connection,
        server_name=server_name.lower(),
    )


def load_all_mcp_tools() -> list[BaseTool]:
    """加载所有已配置的 MCP 服务的工具并合并。

    Returns:
        所有 MCP 服务的工具合并后的列表。
    """
    if not _check_global_enabled():
        logger.debug("MCP 全局开关已关闭，跳过所有 MCP 工具加载")
        return []

    if not _is_mcp_available():
        return []

    all_tools: list[BaseTool] = []
    seen_names: set[str] = set()

    for service_name in _SERVICES:
        tools = load_mcp_tools_for_service(service_name)
        for tool in tools:
            if tool.name in seen_names:
                logger.warning(f"MCP 工具名冲突: '{tool.name}' 已存在，跳过重复注册")
                continue
            seen_names.add(tool.name)
            all_tools.append(tool)

    return all_tools


def shutdown_mcp_clients() -> None:
    """关闭所有 MCP 连接。

    当前实现为按需连接（每次工具调用独立建立 SSE 连接），无持久连接需要关闭。
    保留此函数作为对外接口，未来切换到持久连接模式时实现关闭逻辑。
    """
    pass
