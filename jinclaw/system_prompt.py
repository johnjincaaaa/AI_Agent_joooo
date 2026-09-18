"""
System prompt builder for Jinclaw.
Loads AGENTS.md + MEMORY.md + workspace context → unified system prompt.
"""
from pathlib import Path
from typing import Optional
import os

from paths import resource_path


def _find_project_root() -> Path:
    # 打包后从 _MEIPASS 资源目录读 AGENTS.md
    packaged = resource_path("AGENTS.md")
    if packaged.exists():
        return packaged.parent
    # 开发模式：从 cwd 向上找
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / "AGENTS.md").exists():
            return parent
    return cwd


def load_agents_md() -> str:
    root = _find_project_root()
    agents_path = root / "AGENTS.md"
    if agents_path.exists():
        return agents_path.read_text(encoding="utf-8")
    return _default_agents_content()


def load_memory_md() -> str:
    root = _find_project_root()
    memory_index = root / "memory" / "MEMORY.md"
    if memory_index.exists():
        return memory_index.read_text(encoding="utf-8")
    return ""


def _detect_project_context(workspace_dir: str) -> dict:
    """Auto-detect project type, framework, and key configs for smarter assistance."""
    ctx = {
        "project_type": "unknown",
        "frameworks": [],
        "languages": [],
        "key_files": [],
        "test_commands": [],
        "lint_commands": [],
    }

    ws = Path(workspace_dir)
    if not ws.exists():
        return ctx

    # Language detection
    lang_map = {
        "*.py": "Python",
        "*.js": "JavaScript",
        "*.ts": "TypeScript",
        "*.rs": "Rust",
        "*.go": "Go",
        "*.java": "Java",
        "*.vue": "Vue",
        "*.jsx": "React",
        "*.tsx": "React",
        "*.html": "HTML",
        "*.css": "CSS",
    }

    found_langs = set()
    for pattern, lang in lang_map.items():
        matches = list(ws.rglob(pattern))
        if matches and len(matches) <= 500:  # limit scan
            found_langs.add(lang)
    ctx["languages"] = sorted(found_langs)

    # Project type & framework detection
    indicators = [
        ("package.json", "Node.js/JavaScript project", ["npm install", "npm test"], []),
        ("tsconfig.json", "TypeScript project", ["npm run build", "npx tsc --noEmit"], []),
        ("Cargo.toml", "Rust project", ["cargo test", "cargo check"], ["cargo fmt --check"]),
        ("go.mod", "Go project", ["go test ./...", "go vet ./..."], ["go vet ./..."]),
        ("requirements.txt", "Python project (pip)", [], []),
        ("pyproject.toml", "Python project (pyproject)", ["pytest", "ruff check ."], ["ruff check ."]),
        ("Pipfile", "Python project (pipenv)", [], []),
        ("poetry.lock", "Python project (poetry)", ["pytest", "ruff check ."], ["ruff check ."]),
        ("Makefile", "project with Make", [], []),
        ("docker-compose.yml", "Docker project", ["docker compose up", "docker compose logs"], []),
        ("Dockerfile", "Docker project", ["docker build -t app ."], []),
        ("README.md", "documented project", [], []),
        ("tests/", "has tests", ["pytest"], []),
        ("__tests__/", "has JS tests", ["npm test"], []),
        ("src/", "standard src layout", [], []),
        ("main.py", "FastAPI/Flask app", ["python main.py", "pytest"], []),
        ("app.py", "Flask app", ["python app.py"], []),
    ]

    for fname, ptype, tests, lints in indicators:
        if (ws / fname).exists() or (ws / fname.lower()).exists():
            ctx["key_files"].append(fname)
            if tests:
                ctx["test_commands"].extend(tests)
            if lints:
                ctx["lint_commands"].extend(lints)

    # Framework detection via content scan
    fw_keywords = {
        "FastAPI": ["from fastapi", "import fastapi", "FastAPI("],
        "Flask": ["from flask", "import flask", "Flask(__name__)"],
        "Django": ["from django", "import django"],
        "SQLAlchemy": ["from sqlalchemy", "import sqlalchemy"],
        "React": ["react", "@types/react"],
        "Vue": ["vue", "@vue"],
        "Vite": ["vite"],
        "Tauri": ["tauri.conf", "@tauri-apps"],
        "LangChain": ["langchain", "from langchain"],
    }

    for fname in ["requirements.txt", "pyproject.toml", "package.json", "Cargo.toml"]:
        fpath = ws / fname
        if fpath.exists():
            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore").lower()
                for fw, keywords in fw_keywords.items():
                    if any(kw.lower() in content for kw in keywords):
                        if fw not in ctx["frameworks"]:
                            ctx["frameworks"].append(fw)
            except Exception:
                pass

    # Determine primary project type
    if ctx["frameworks"]:
        ctx["project_type"] = f"{', '.join(ctx['frameworks'])} project"
    elif ctx["languages"]:
        ctx["project_type"] = f"{'/'.join(ctx['languages'])} project"

    return ctx


def build_system_prompt(
    workspace_dir: Optional[str] = None,
    lang: str = "zh",
) -> str:
    parts = []

    # 1. Core agent definition (AGENTS.md)
    agents_content = load_agents_md()
    parts.append(agents_content)

    # 2. Language directive
    if lang.startswith("zh"):
        parts.append("\n## 当前会话语言\n请使用中文与用户交流。代码和报错信息保持原样。")
    else:
        parts.append("\n## Current Session Language\nPlease communicate in English.")

    # 3. Memory context
    memory_content = load_memory_md()
    if memory_content.strip():
        parts.append("\n## 跨会话记忆\n以下信息跨会话持久化，用于提供个性化协助：\n")
        parts.append(memory_content)

    # 4. Workspace + project context
    if workspace_dir:
        abs_ws = os.path.abspath(workspace_dir)
        project_ctx = _detect_project_context(abs_ws)

        parts.append(f"""
## 🔒 工作目录

当前工作目录：`{abs_ws}`

**必须遵守：**
- 所有文件操作默认在此目录下进行，用户说"当前目录"→就是这里
- 创建文件时用户未指定路径→直接在此创建，不要提问
- Shell 命令的工作目录已绑定到此

## 📁 项目上下文（自动检测）

- 项目类型：{project_ctx['project_type']}
- 涉及语言：{', '.join(project_ctx['languages']) or '未检测到'}
- 使用框架：{', '.join(project_ctx['frameworks']) or '未检测到'}
- 关键文件：{', '.join(project_ctx['key_files']) or '未检测到'}
- 测试命令：{', '.join(project_ctx['test_commands']) or '未检测到'}
- Lint 命令：{', '.join(project_ctx['lint_commands']) or '未检测到'}

**利用这些信息：**
- 根据项目类型推荐合适的实现方式
- 使用检测到的测试命令验证你的改动
- 遵循项目已有的框架和约定
""")
    else:
        parts.append("""
## ⚠️ 无工作目录
当前没有绑定工作目录。请提示用户先打开一个文件夹。
""")

    # 5. Available tools with usage guide
    parts.append("""
## 🛠 可用工具

### 本地 MCP 工具（桌面端专属）
- `mcp_file_read` / `mcp_file_write` / `mcp_file_list` — 文件读写操作
- `mcp_shell_exec` — 执行 Shell 命令（已自动设置工作目录）
- `mcp_git_status` / `mcp_git_commit` / `mcp_git_log` — Git 操作
- `mcp_browser_navigate` / `mcp_browser_snapshot` / `mcp_browser_click` — 浏览器自动化
- `mcp_db_query` / `mcp_db_tables` — 数据库查询

### 云端工具
- `web_search` — 搜索网络
- `code_exec` — 在沙箱中执行 Python 代码
- `image_parsing` — 分析图片内容
- `document_parsing` — 解析 PDF/DOCX 文档
- `http_request` — 发送 HTTP 请求

### 工具组合示例
```
查找函数定义 → grep "def function_name"
理解上下文 → read 相关文件
修改实现 → edit/write 文件
验证改动 → shell 运行测试命令
提交代码 → git_commit + git_push
```

### 重要规则
- **先读后写**：编辑前必须先读取文件当前内容
- **精确编辑**：小改动用 edit，大重写用 write
- **执行验证**：改完代码后运行相关命令确认无误
- **错误分析**：遇到报错先分析原因，不要盲目重试
""")

    return "\n".join(parts)


def _default_agents_content() -> str:
    return """# Jinclaw — Senior Coding Agent

You are Jinclaw, a senior full-stack engineer proficient in Python/TypeScript/Rust.

## Working Style
- **Understand first** — search, read, analyze before writing code
- **Plan before execute** — list files to change, explain why, estimate risk
- **Verify after change** — run tests, check types, confirm no regression
- **Explain concisely** — what changed, why, how to verify

## Core Principles
- Minimal changes, maximum clarity
- Match existing patterns and conventions
- Never guess — search or read when uncertain
- Code quality > speed
"""
