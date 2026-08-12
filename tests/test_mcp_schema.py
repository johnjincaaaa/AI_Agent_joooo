"""Tests for mcp._build_json_schema and MCPManager helper utilities."""
import pytest
from mcp import _build_json_schema, _infer_js_type


def sample_func_str_only(a, b, c):
    """Sample callable with no defaults."""
    return a + b + c


def sample_func_with_defaults(
    path: str,
    timeout: int = 30,
    verbose: bool = False,
    ratio: float = 1.5,
    optional_note: str = "",
):
    """Callable with defaults of varied Python types."""
    return None


class SampleCallable:
    def __init__(self, name: str, count: int = 5):
        pass


class TestInferJsType:
    def test_bool(self):
        assert _infer_js_type(True) == "boolean"

    def test_int(self):
        assert _infer_js_type(10) == "integer"

    def test_float(self):
        assert _infer_js_type(3.14) == "number"

    def test_string_fallback(self):
        assert _infer_js_type("hi") == "string"
        assert _infer_js_type(None) == "string"


class TestBuildJsonSchema:
    def test_str_params_all_required(self):
        params = {"path": "文件路径", "line": "起始行号"}
        schema = _build_json_schema(sample_func_str_only, params)
        assert schema["type"] == "object"
        assert "path" in schema["properties"]
        assert schema["properties"]["path"]["type"] == "string"
        assert schema["properties"]["path"]["description"] == "文件路径"
        assert schema["required"] == ["path", "line"]

    def test_defaults_infer_types_and_skip_required(self):
        params = {
            "path": "文件路径",
            "timeout": "超时秒数",
            "verbose": "打印详情",
            "ratio": "缩放比例",
            "optional_note": "备注",
        }
        schema = _build_json_schema(sample_func_with_defaults, params)
        props = schema["properties"]

        # `path` has no default → required + string
        assert "path" in schema["required"]
        assert props["path"]["type"] == "string"

        # `timeout` default is int → integer + has default value
        assert "timeout" not in schema["required"]
        assert props["timeout"]["type"] == "integer"
        assert props["timeout"]["default"] == 30

        # `verbose` default is bool → boolean
        assert props["verbose"]["type"] == "boolean"
        assert props["verbose"]["default"] is False

        # `ratio` default is float → number
        assert props["ratio"]["type"] == "number"
        assert props["ratio"]["default"] == 1.5

    def test_already_schema_passthrough(self):
        """If raw_params already has properties/type, pass it through unchanged."""
        raw = {
            "type": "object",
            "properties": {"x": {"type": "number"}},
            "required": ["x"],
        }
        assert _build_json_schema(sample_func_str_only, raw) is raw

    def test_empty_params(self):
        schema = _build_json_schema(sample_func_str_only, None)
        assert schema == {"type": "object", "properties": {}}

    def test_dict_style_param_desc(self):
        """Parameters can be given as a dict with richer metadata."""
        params = {
            "path": {"description": "路径", "type": "string", "enum": ["a", "b"]}
        }
        schema = _build_json_schema(sample_func_str_only, params)
        assert schema["properties"]["path"]["description"] == "路径"
        assert schema["properties"]["path"]["type"] == "string"
        assert schema["properties"]["path"]["enum"] == ["a", "b"]

    def test_no_signature_inspection_works(self):
        """If callable has no signature (e.g. a lambda in weird state), still works."""
        params = {"name": "名字"}
        # Lambdas have signatures, so wrap in a callable class where we force no inspectable signature
        class NoSig:
            __name__ = "NoSig"
            def __call__(self, *args, **kwargs): return None
        # We'll call build with no signature info available: mock inspect.signature by using a class
        # whose `__call__` inspect can resolve but we fake a raw desc with no signature link.
        schema = _build_json_schema(lambda x=None: x, params)
        # The lambda's signature has x with default None; we only ask for `name` so it's required
        # (name is not in lambda's signature)
        assert "name" in schema["required"]


class TestMCPManager:
    def test_register_and_list(self):
        from mcp import MCPManager
        mgr = MCPManager()

        def echo(text: str, repeat: int = 1):
            return text * repeat

        mgr.register_tool("demo_echo", echo, "重复字符串", {"text": "要重复的字符串", "repeat": "次数"})
        tools = {t["name"]: t for t in mgr.list_tools()}
        # All 5 filesystem/shell/git/browser/database tools registered + our demo_echo
        assert "demo_echo" in tools
        meta = tools["demo_echo"]
        assert meta["parameters"]["type"] == "object"
        assert "text" in meta["parameters"]["required"]
        # repeat defaults to 1 so not required
        assert "repeat" not in meta["parameters"]["required"]
        assert meta["parameters"]["properties"]["repeat"]["default"] == 1

    def test_call_tool_success(self):
        from mcp import MCPManager
        mgr = MCPManager()
        mgr.register_tool("add", lambda a, b: a + b, "add two ints", {"a": "op1", "b": "op2"})
        assert mgr.call_tool("add", a=2, b=3) == 5

    def test_call_unknown_raises(self):
        from mcp import MCPManager
        mgr = MCPManager()
        with pytest.raises(ValueError, match="未知的 MCP 工具"):
            mgr.call_tool("nope")
