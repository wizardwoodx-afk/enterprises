"""MCP (Model Context Protocol) client support for Beholders agents.

This module provides native MCP client functionality, allowing Beholders agents
to connect to any MCP-compliant server using various transport types.

Heavy imports (MCPClient, MCPToolResolver, BaseTransport, TransportType) are
lazy-loaded on first access to avoid pulling in the ``mcp`` SDK (~400ms)
when only lightweight config/filter types are needed.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from beholders.mcp.config import (
    MCPServerConfig,
    MCPServerHTTP,
    MCPServerSSE,
    MCPServerStdio,
)
from beholders.mcp.filters import (
    StaticToolFilter,
    ToolFilter,
    ToolFilterContext,
    create_dynamic_tool_filter,
    create_static_tool_filter,
)


if TYPE_CHECKING:
    from beholders.mcp.client import MCPClient
    from beholders.mcp.tool_resolver import MCPToolResolver
    from beholders.mcp.transports.base import BaseTransport, TransportType

_LAZY: dict[str, tuple[str, str]] = {
    "MCPClient": ("beholders.mcp.client", "MCPClient"),
    "MCPToolResolver": ("beholders.mcp.tool_resolver", "MCPToolResolver"),
    "BaseTransport": ("beholders.mcp.transports.base", "BaseTransport"),
    "TransportType": ("beholders.mcp.transports.base", "TransportType"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        mod_path, attr = _LAZY[name]
        mod = importlib.import_module(mod_path)
        val = getattr(mod, attr)
        globals()[name] = val  # cache for subsequent access
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BaseTransport",
    "MCPClient",
    "MCPServerConfig",
    "MCPServerHTTP",
    "MCPServerSSE",
    "MCPServerStdio",
    "MCPToolResolver",
    "StaticToolFilter",
    "ToolFilter",
    "ToolFilterContext",
    "TransportType",
    "create_dynamic_tool_filter",
    "create_static_tool_filter",
]
