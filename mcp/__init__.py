"""
本地 MCP 服务管理器：统一管理所有本地 MCP 工具。
桌面端可用：FileSystem、Shell、Git、Browser、Database
"""
from typing import Dict, Any, Callable, Optional
import inspect
import logging

logger = logging.getLogger(__name__)

# ── helpers ────────────────────────────────────────────────────────

def _infer_js_type(python_default: Any) -> str:
    """根据默认值推断 JSON Schema 类型。"""
    if isinstance(python_default, bool):
        return "boolean"
    if isinstance(python_default, int):
        return "integer"
    if isinstance(python_default, float):
        return "number"
    return "string"


def _build_json_schema(func: Callable, raw_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 MCP 注册时传入的简单参数描述（{name: desc}）转换为合法的 JSON Schema。
    自动结合函数签名识别默认值、类型、required 字段。
    """
    try:
        sig = inspect.signature(func)
    except (ValueError, TypeError):
        sig = None

    properties: Dict[str, Any] = {}
    required: list = []

    # 如果 raw_params 已经是合法 JSON Schema（已有 properties），直接返回
    if isinstance(raw_params, dict) and "properties" in raw_params and "type" in raw_params:
        return raw_params

    for param_name, param_desc in (raw_params or {}).items():
        # 获取默认值和类型
        default_sentinel = inspect.Parameter.empty
        param_type = "string"
        default_value = None
        has_default = False

        if sig is not None and param_name in sig.parameters:
            p = sig.parameters[param_name]
            if p.default is not inspect.Parameter.empty:
                default_sentinel = p.default
                default_value = p.default
                has_default = True
                param_type = _infer_js_type(p.default)

        prop: Dict[str, Any] = {"type": param_type}
        if isinstance(param_desc, str):
            prop["description"] = param_desc
        elif isinstance(param_desc, dict):
            # 已经是属性定义了
            prop = {**param_desc, "type": param_desc.get("type", param_type)}

        if has_default:
            prop["default"] = default_value
        else:
            required.append(param_name)

        properties[param_name] = prop

    schema = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


# ── Manager ────────────────────────────────────────────────────────

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
        from .filesystem_mcp import register_filesystem_tools
        from .shell_mcp import register_shell_tools
        from .git_mcp import register_git_tools
        from .browser_mcp import register_browser_tools
        from .database_mcp import register_database_tools

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
