"""
MCP 工具注册时的 JSON Schema 推断辅助 —— 从 mcp/__init__.py 拆出。
"""
from typing import Dict, Any, Callable
import inspect


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
        param_type = "string"
        default_value = None
        has_default = False

        if sig is not None and param_name in sig.parameters:
            p = sig.parameters[param_name]
            if p.default is not inspect.Parameter.empty:
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
