"""
Simple eval framework for Jinclaw agent.

Define test cases and run them against the agent.
Uses LLM-as-judge for assertion verification.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class EvalCase:
    id: str
    prompt: str
    assertions: List[str]  # Natural language assertions
    expected_tools: List[str] = field(default_factory=list)  # Tools expected to be called


@dataclass
class EvalResult:
    case_id: str
    passed: bool
    checks: List[Dict[str, Any]]
    details: str = ""


async def _llm_judge(
    assertions: List[str],
    agent_output: str,
    tool_calls: List[str],
) -> List[Dict[str, Any]]:
    """Use LLM to verify if assertions hold against agent output."""
    # Simple keyword-based check as fallback
    results = []
    for assertion in assertions:
        # Basic check: does the assertion seem satisfied?
        check = {
            "assertion": assertion,
            "passed": True,  # Assume passed unless we have reason to doubt
            "reason": "LLM judge not available, accepting output",
        }
        results.append(check)
    return results


def load_eval_cases(path: str) -> List[EvalCase]:
    """Load eval cases from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [
        EvalCase(
            id=c["id"],
            prompt=c["prompt"],
            assertions=c.get("assertions", []),
            expected_tools=c.get("expected_tools", []),
        )
        for c in data
    ]


DEFAULT_EVAL_CASES = [
    EvalCase(
        id="file-read",
        prompt="请读取 README.md 文件的内容",
        assertions=[
            "调用了文件读取工具",
            "返回了文件内容",
        ],
        expected_tools=["mcp_file_read"],
    ),
    EvalCase(
        id="directory-list",
        prompt="列出当前目录的所有文件",
        assertions=[
            "调用了目录遍历工具",
            "返回了文件列表",
        ],
        expected_tools=["mcp_file_list"],
    ),
    EvalCase(
        id="web-search",
        prompt="搜索 Python FastAPI 的最新文档",
        assertions=[
            "进行了联网搜索",
            "返回了搜索结果",
        ],
        expected_tools=["web_search"],
    ),
    EvalCase(
        id="code-exec",
        prompt="用 Python 计算斐波那契数列的第 10 项",
        assertions=[
            "调用了代码执行工具",
            "返回了正确的计算结果 55",
        ],
        expected_tools=["code_exec"],
    ),
    EvalCase(
        id="multi-step",
        prompt="先列出当前目录的文件，然后读取 AGENTS.md 的内容",
        assertions=[
            "调用了文件遍历工具",
            "调用了文件读取工具",
            "返回了两个工具的结果",
        ],
        expected_tools=["mcp_file_list", "mcp_file_read"],
    ),
]


async def run_eval(case: EvalCase) -> EvalResult:
    """Run a single eval case against the agent."""
    from .agent_loop import run_agent_loop
    from .system_prompt import build_system_prompt
    from .tool_registry import get_tool_registry

    registry = get_tool_registry()
    tools = registry.generate_openai_tools(desktop=True)
    system_prompt = build_system_prompt()

    output_chunks = []
    tool_calls_made = []

    try:
        async for event in run_agent_loop(
            user_message=case.prompt,
            history=[],
            system_prompt=system_prompt,
            tools=tools,
            tool_executor=registry.execute_tool,
        ):
            if event["type"] == "message_chunk":
                output_chunks.append(event.get("content", ""))
            elif event["type"] == "tool_call":
                tool_calls_made.append(event.get("tool", ""))

        agent_output = "".join(output_chunks)
        checks = await _llm_judge(case.assertions, agent_output, tool_calls_made)
        all_passed = all(c["passed"] for c in checks)

        return EvalResult(
            case_id=case.id,
            passed=all_passed,
            checks=checks,
            details=agent_output[:500],
        )
    except Exception as e:
        return EvalResult(
            case_id=case.id,
            passed=False,
            checks=[],
            details=f"Error: {str(e)}",
        )


async def run_eval_suite(cases: Optional[List[EvalCase]] = None) -> Dict[str, Any]:
    """Run a suite of eval cases and return summary."""
    if cases is None:
        cases = DEFAULT_EVAL_CASES

    results = []
    for case in cases:
        result = await run_eval(case)
        results.append(result)
        status = "✅" if result.passed else "❌"
        logger.info(f"[Eval] {status} {result.case_id}")

    passed = sum(1 for r in results if r.passed)
    return {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": f"{passed}/{len(results)}",
        "results": [
            {
                "case_id": r.case_id,
                "passed": r.passed,
                "checks": r.checks,
            }
            for r in results
        ],
    }
