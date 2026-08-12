"""
Unified tool registry for Jinclaw agent.

Aggregates all available tools from:
- MCP modules (FileSystem, Shell, Git, Browser, Database)
- Cloud skills (web_search, code_exec, image_parsing, document_parsing, etc.)
- System tools (memory save/load, etc.)
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolDef:
    """Tool definition for the agent to consume."""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema for function calling
    category: str  # "mcp" | "cloud" | "system"
    execute: Callable
    desktop_only: bool = False


class ToolRegistry:
    """Unified tool registry aggregating MCP + cloud + system tools."""

    def __init__(self):
        self._tools: Dict[str, ToolDef] = {}
        self._register_mcp_tools()
        self._register_cloud_tools()

    # ── registration ──────────────────────────────────────────

    def register(self, tool: ToolDef):
        self._tools[tool.name] = tool
        logger.debug(f"[ToolRegistry] registered: {tool.name}")

    def get(self, name: str) -> Optional[ToolDef]:
        return self._tools.get(name)

    def list_all(self, desktop: bool = True) -> List[Dict[str, Any]]:
        """Return tool list for frontend display / LLM consumption."""
        result = []
        for t in self._tools.values():
            if t.desktop_only and not desktop:
                continue
            result.append({
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
                "category": t.category,
                "desktop_only": t.desktop_only,
            })
        return result

    def get_categories(self) -> Dict[str, str]:
        return {
            "mcp": "本地 MCP",
            "cloud": "云端 Skill",
            "system": "系统",
        }

    # ── execution ──────────────────────────────────────────────

    def execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        """Execute a tool by name with given arguments. Returns result string."""
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Unknown tool '{name}'"
        try:
            result = tool.execute(**args)
            # Truncate very long results
            result_str = str(result)
            if len(result_str) > 8000:
                result_str = result_str[:8000] + "\n...(truncated)"
            return result_str
        except Exception as e:
            logger.error(f"[ToolRegistry] {name} failed: {e}")
            return f"Error executing {name}: {str(e)}"

    # ── MCP tools ──────────────────────────────────────────────

    def _register_mcp_tools(self):
        """Register all 5 MCP module tools as desktop-only."""
        try:
            from mcp import get_mcp_manager
            mcp = get_mcp_manager()
            for meta in mcp.list_tools():
                tool_name = meta["name"]  # capture for closure
                def _make_exec(name):
                    return lambda **kw: mcp.call_tool(name, **kw)
                self.register(ToolDef(
                    name=tool_name,
                    description=meta.get("description", ""),
                    parameters=meta.get("parameters", {}),
                    category="mcp",
                    execute=_make_exec(tool_name),
                    desktop_only=True,
                ))
            logger.info(f"[ToolRegistry] loaded {len(mcp.list_tools())} MCP tools")
        except Exception as e:
            logger.warning(f"[ToolRegistry] MCP tools unavailable: {e}")

    # ── cloud / skill tools ───────────────────────────────────

    def _register_cloud_tools(self):
        """Register cloud-accessible tools (web search, code sandbox, etc.)."""

        # Web search
        try:
            from tools import online
            self.register(ToolDef(
                name="web_search",
                description="Search the web using Bing. Returns top results with title, snippet, and URL.",
                parameters={
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string", "description": "Search query keywords"},
                    },
                    "required": ["keyword"],
                },
                category="cloud",
                execute=lambda keyword: online.invoke(keyword) if hasattr(online, 'invoke') else online(keyword),
            ))
        except Exception as e:
            logger.warning(f"[ToolRegistry] web_search unavailable: {e}")

        # Code sandbox
        try:
            from tools.tool_code_sandbox import run_python_code
            self.register(ToolDef(
                name="code_exec",
                description="Execute Python code in an isolated sandbox. Input data is available as the 'input' variable. Assign result to 'result' variable.",
                parameters={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "Python code to execute"},
                        "input_data": {"type": "string", "description": "Optional input data to pass to the sandbox"},
                    },
                    "required": ["code"],
                },
                category="cloud",
                execute=lambda code, input_data="": self._run_sandbox(code, input_data),
            ))
        except Exception as e:
            logger.warning(f"[ToolRegistry] code_exec unavailable: {e}")

        # Image parsing
        try:
            from tools.tool_Image_parsing import image_analyze
            self.register(ToolDef(
                name="image_parsing",
                description="Analyze an image file: extract metadata (size, format, colors) and describe content using AI vision.",
                parameters={
                    "type": "object",
                    "properties": {
                        "image_path": {"type": "string", "description": "Path to the image file"},
                    },
                    "required": ["image_path"],
                },
                category="cloud",
                execute=lambda image_path: image_analyze.invoke(image_path),
            ))
        except Exception as e:
            logger.warning(f"[ToolRegistry] image_parsing unavailable: {e}")

        # Document parsing
        try:
            from tools.tool_document_parsing import document_analyze
            self.register(ToolDef(
                name="document_parsing",
                description="Read and extract text from documents: PDF, DOCX, TXT files.",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to the document file"},
                    },
                    "required": ["file_path"],
                },
                category="cloud",
                execute=lambda file_path: document_analyze.invoke(file_path),
            ))
        except Exception as e:
            logger.warning(f"[ToolRegistry] document_parsing unavailable: {e}")

        # HTTP request
        self.register(ToolDef(
            name="http_request",
            description="Make an HTTP request to a given URL. Supports GET, POST, PUT, DELETE methods.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Target URL"},
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"], "description": "HTTP method"},
                },
                "required": ["url"],
            },
            category="cloud",
            execute=lambda url, method="GET": self._http_request(url, method),
        ))

    @staticmethod
    def _run_sandbox(code: str, input_data: str = "") -> str:
        from tools.tool_code_sandbox import run_python_code
        result = run_python_code(code, input_data=input_data)
        if result.get("success"):
            out = result.get("output", "")
            val = result.get("result")
            if val is not None:
                out += f"\nresult = {val}"
            return out
        return f"Error: {result.get('error', 'unknown')}"

    @staticmethod
    def _http_request(url: str, method: str = "GET") -> str:
        import requests
        try:
            if method == "GET":
                resp = requests.get(url, timeout=30)
            elif method == "POST":
                resp = requests.post(url, timeout=30)
            elif method == "PUT":
                resp = requests.put(url, timeout=30)
            elif method == "DELETE":
                resp = requests.delete(url, timeout=30)
            else:
                return f"Unsupported method: {method}"
            return f"HTTP {resp.status_code}\n{resp.text[:5000]}"
        except Exception as e:
            return f"HTTP request failed: {e}"

    # ── OpenAI-compatible schema generation ────────────────────

    def generate_openai_tools(self, desktop: bool = True) -> List[Dict[str, Any]]:
        """Generate OpenAI-compatible tool/function definitions."""
        tools = []
        for t in self._tools.values():
            if t.desktop_only and not desktop:
                continue
            tools.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters if t.parameters else {"type": "object", "properties": {}},
                }
            })
        return tools


# ── global singleton ────────────────────────────────────────────

_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
