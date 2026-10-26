"""
本地 MCP 服务管理器：统一管理所有本地 MCP 工具。
桌面端可用：FileSystem、Shell、Git、Browser、Database
"""
from typing import Dict, Any, Callable, Optional
import logging

from app.mcp._schema import _build_json_schema

logger = logging.getLogger(__name__)


class MCPManager:
    """MCP 工具管理器，注册和调度所有本地 MCP 工具。"""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._tool_meta: Dict[str, Dict[str, Any]] = {}
        self._register_default_tools()

    def register_tool(self, name: str, func: Callable, description: str = "",
                       parameters: Optional[Dict[str, Any]] = None):
        """注册一个 MCP 工具（parameters 自动转换为 JSON Schema）。"""
        self._tools[name] = func
        self._tool_meta[name] = {
            "name": name,
            "description": description,
            "parameters": _build_json_schema(func, parameters or {}),
        }
        logger.info(f"[MCP] 注册工具: {name}")

    def list_tools(self) -> list:
        """列出所有可用工具（parameters 为 JSON Schema）。"""
        return list(self._tool_meta.values())

    def tool_names(self) -> list:
        return list(self._tools.keys())

    def call_tool(self, name: str, **kwargs) -> Any:
        """调用指定的 MCP 工具。"""
        if name not in self._tools:
            raise ValueError(f"未知的 MCP 工具: {name}")
        logger.info(f"[MCP] 调用工具: {name} | 参数: {list(kwargs.keys())}")
        try:
            result = self._tools[name](**kwargs)
            return result
        except Exception as e:
            logger.error(f"[MCP] 工具 {name} 执行失败: {e}")
            raise

    def _register_default_tools(self):
        """注册所有默认的 MCP 工具。"""
        from app.mcp.filesystem_mcp import register_filesystem_tools
        from app.mcp.shell_mcp import register_shell_tools
        from app.mcp.git_mcp import register_git_tools
        from app.mcp.browser_mcp import register_browser_tools
        from app.mcp.database_mcp import register_database_tools

        register_filesystem_tools(self)
        register_shell_tools(self)
        register_git_tools(self)
        register_browser_tools(self)
        register_database_tools(self)


# 全局单例
_mcp_manager: Optional[MCPManager] = None


def get_mcp_manager() -> MCPManager:
    """获取 MCP 管理器单例。"""
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPManager()
    return _mcp_manager
