"""
Jinclaw Agent Loop — Code-first agent with structured execution.

Flow: user message → explore codebase → make plan → execute step by step → verify → report
"""
from typing import AsyncGenerator, Dict, Any, List, Optional
import json, logging, re, os
import config

logger = logging.getLogger(__name__)
MAX_TOOL_ROUNDS = 30

# ── Code task patterns that require exploration before execution ──
CODE_TASK_KEYWORDS = [
    "代码", "函数", "类", "方法", "bug", "错误", "报错", "异常",
    "fix", "修", "改", "加", "删", "实现", "功能", "接口",
    "function", "class", "method", "error", "bug", "fix",
    "implement", "refactor", "debug", "test", "import",
    "api", "路由", "数据库", "sql", "查询",
    "组件", "页面", "样式", "样式", "前端", "后端",
    "配置", "依赖", "安装", "package", "pip",
    "构建", "编译", "运行", "启动",
]


def _is_code_task(message: str) -> bool:
    """Detect if the user message is a code-related task requiring structured workflow."""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in CODE_TASK_KEYWORDS)


async def run_agent_loop(
    user_message: str,
    history: List[Dict[str, Any]],
    system_prompt: str,
    tools: List[Dict[str, Any]],
    tool_executor,
    lang: str = "zh",
) -> AsyncGenerator[Dict[str, Any], None]:
    """Code-first agent: explore → plan → execute → verify."""

    is_en = lang.lower().startswith("en")
    is_code_task = _is_code_task(user_message)

    messages = [{"role": "system", "content": system_prompt}]
    recent = history[-40:] if history else []
    for msg in recent:
        role = msg.get("role", "user")
        content = msg.get("message") or msg.get("content") or ""
        if role == "user":
            messages.append({"role": "user", "content": content})
        elif role in ("ai", "assistant"):
            messages.append({"role": "assistant", "content": content})

    # Build the task prompt based on whether it's a code task
    if is_code_task:
        task_prompt = f"""
## 代码任务

用户需求：{user_message}

### 执行流程（严格按顺序）

**Step 1: 探索代码**
在写任何代码之前，先做以下事情：
1. 用 `mcp_shell_exec` 执行 grep/search 搜索相关函数、类、文件
2. 用 `mcp_file_read` 读取找到的相关文件，理解现有实现
3. 识别项目的代码风格、命名规范、架构模式
4. 输出你的理解摘要

**Step 2: 制定计划**
基于探索结果，制定执行计划：
```plan
1. [要修改的文件和原因]
2. [要创建的新文件]
3. [具体改动点]
4. [验证方式]
```

**Step 3: 执行改动**
按计划逐步执行，每一步：
- 读取当前文件内容
- 精确改动
- 说明改了什么

**Step 4: 验证**
完成后必须：
- 运行测试或构建命令确认无误
- 检查是否有遗漏
- 总结改动点

现在开始 Step 1：探索代码。
"""
    else:
        task_prompt = f"""
用户需求：{user_message}

请先制定执行计划，然后开始执行。用以下格式回复：
```plan
1. [步骤1描述]
2. [步骤2描述]
...
```
然后开始执行。
"""

    messages.append({"role": "user", "content": task_prompt})

    tool_call_count = 0
    plan_items = []
    executed_steps = []
    verification_done = False

    try:
        from langchain.chat_models import init_chat_model
        from langchain.messages import ToolMessage, AIMessage, HumanMessage

        model = init_chat_model(
            model=config.MODEL, model_provider="openai",
            base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY,
            temperature=0.7,
        )
        model_with_tools = model.bind_tools(tools)

        for turn in range(MAX_TOOL_ROUNDS):
            yield {"type": "thinking"}

            try:
                response = model_with_tools.invoke(messages)
                messages.append(response)

                text = getattr(response, "content", "") or ""

                # Extract plan
                plan_match = re.search(r'```plan\s*\n(.*?)```', text, re.DOTALL)
                if plan_match and not plan_items:
                    raw = plan_match.group(1).strip()
                    plan_items = [l.lstrip('0123456789. )-') for l in raw.split('\n') if l.strip()]
                    yield {"type": "plan", "items": plan_items, "content": text.replace(plan_match.group(0), '').strip()}

                # Track verification phase
                if is_code_task and not verification_done:
                    if any(kw in text.lower() for kw in ["验证", "verify", "测试", "test", "完成", "done"]):
                        verification_done = True
                        yield {"type": "phase", "phase": "verification", "content": text}

                # Check for tool calls
                tool_calls = getattr(response, "tool_calls", None) or []
                if tool_calls:
                    for tc in tool_calls:
                        tool_name = tc.get("name", "")
                        tool_args = tc.get("args", {})
                        yield {"type": "tool_call", "tool": tool_name, "args": tool_args}

                        try:
                            result_str = tool_executor(tool_name, tool_args)
                        except Exception as e:
                            result_str = f"Tool error: {str(e)}"

                        tool_call_count += 1

                        # Smart result summarization for code tasks
                        if is_code_task and len(result_str) > 3000:
                            result_str = result_str[:2000] + "\n...(截断)..." + result_str[-500:]

                        yield {"type": "tool_result", "tool": tool_name, "result": result_str}
                        messages.append(ToolMessage(content=str(result_str), tool_call_id=tc.get("id", f"call_{turn}")))

                else:
                    content = text
                    if content:
                        yield {"type": "message_chunk", "content": content}
                    yield {"type": "done", "tool_calls": tool_call_count, "plan_items": plan_items}
                    return

            except Exception as e:
                logger.error(f"[AgentLoop] turn {turn}: {e}")
                yield {"type": "error", "content": str(e)}
                break

        # If we exhausted all turns, provide a summary
        yield {"type": "done", "tool_calls": tool_call_count, "plan_items": plan_items}

    except Exception as e:
        logger.error(f"[AgentLoop] fatal: {e}")
        yield {"type": "error", "content": str(e)}


class AgentLoop:
    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = workspace_dir or "."

    async def stream(self, user_message, history, session_id=None, user_id=None, lang="zh"):
        from .system_prompt import build_system_prompt
        from .tool_registry import get_tool_registry

        registry = get_tool_registry()
        ws = self.workspace_dir if self.workspace_dir and self.workspace_dir != "." else None
        system_prompt = build_system_prompt(workspace_dir=ws, lang=lang)
        tools = registry.generate_openai_tools(desktop=True)

        def workspace_executor(name, args):
            if ws and name.startswith("mcp_file"):
                p = args.get("path", "")
                # Relativize: if the path looks like an absolute Python cwd, fix it
                if not p or p == "." or (p.startswith("D:") and not p.startswith(ws[:3])):
                    args = dict(args)
                    args["path"] = ws
                elif p and not (p.startswith("/") or p.startswith("\\") or ":" in p):
                    args = dict(args)
                    args["path"] = os.path.join(ws, p)
            if ws and name == "mcp_shell_exec":
                if "cwd" not in args or args.get("cwd") in (".", ""):
                    args = dict(args)
                    args["cwd"] = ws
            return registry.execute_tool(name, args)

        async for event in run_agent_loop(
            user_message=user_message, history=history,
            system_prompt=system_prompt, tools=tools,
            tool_executor=workspace_executor, lang=lang,
        ):
            yield event
