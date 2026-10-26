"""本地 MCP 工具包（FileSystem/Shell/Git/Browser/Database）。"""
from .manager import MCPManager, get_mcp_manager
from ._schema import _build_json_schema, _infer_js_type

__all__ = ["MCPManager", "get_mcp_manager", "_build_json_schema", "_infer_js_type"]
