"""
Jinclaw Coding Agent routes — extracted from main.py.

All endpoints live under:
- Page:     GET  /jinclaw
- Tools:    GET  /ai/jinclaw/tools
- Memory:   GET/POST/DELETE  /ai/jinclaw/memories*
- Chat:     POST /ai/jinclaw/chat          (SSE stream)
- Projects: CRUD /ai/jinclaw/projects*
- Tasks:    CRUD /ai/jinclaw/tasks*
- Workspace: GET /ai/jinclaw/workspace/{tree,read}
- Diffs:    CRUD /ai/jinclaw/diffs*
- Shell:    GET  /ai/jinclaw/shell
"""
import json
import logging
import os
import subprocess
import uuid as _uuid
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, HTTPException, Query, Request,
    UploadFile, File,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import config
from jinclaw.agent_loop import AgentLoop
from jinclaw.memory import MemoryStore
from jinclaw.storage import JingentStorage
from jinclaw.tool_registry import get_tool_registry
from token_utils import get_optional_user_id
from rate_limit import check_anonymous_rate_limit, get_anonymous_remaining


logger = logging.getLogger(__name__)
router = APIRouter()


# Re-exported helpers so main.py doesn't need to duplicate these.
# They reference globals set by main.py before `include_router`.
_templates_ref: Optional[object] = None  # Jinja2Templates
_chat_access_fn: Optional[callable] = None  # ensure_chat_access


def bind(templates, ensure_chat_access_fn):
    """Must be called from main.py before including the router."""
    global _templates_ref, _chat_access_fn
    _templates_ref = templates
    _chat_access_fn = ensure_chat_access_fn


# ==================================================================
# Request models
# ==================================================================

class ChatMessage(BaseModel):
    role: str = ""
    message: str = ""


class JinclawChatRequest(BaseModel):
    history: List[ChatMessage] = []
    newMessage: str = ""
    task_id: Optional[str] = None
    lang: str = "zh"


class JinclawSaveRequest(BaseModel):
    type: str = ""
    role: str = ""
    message: str = ""


class DiffSaveRequest(BaseModel):
    task_id: str
    file_path: str
    patch: str


class WorkspaceFsActionRequest(BaseModel):
    action: str   # "explore" | "rename" | "delete"
    path: str
    new_name: Optional[str] = None


# ==================================================================
# Page
# ==================================================================

@router.get("/jinclaw", summary="Jinclaw Coding Agent 页面")
def jinclaw_page(request: Request):
    return _templates_ref.TemplateResponse(name="jinclaw.html", request=request)


# ==================================================================
# Tools
# ==================================================================

@router.get("/ai/jinclaw/tools", summary="获取 Jinclaw 可用工具列表")
def jinclaw_tools(desktop: bool = Query(True)):
    registry = get_tool_registry()
    return {
        "code": 200,
        "tools": registry.list_all(desktop=desktop),
        "categories": registry.get_categories(),
    }


# ==================================================================
# Memories
# ==================================================================

@router.get("/ai/jinclaw/memories", summary="获取持久记忆")
def jinclaw_memories():
    store = MemoryStore()
    return {"code": 200, "memories": store.list_all(), "count": store.count}


@router.post("/ai/jinclaw/memories", summary="保存记忆")
def jinclaw_save_memory(
    title: str = Query(...),
    content: str = Query(...),
    description: str = Query(""),
):
    store = MemoryStore()
    slug = store.save(title=title, content=content, description=description)
    return {"code": 200, "msg": "记忆已保存", "slug": slug}


@router.delete("/ai/jinclaw/memories/{slug}", summary="删除记忆")
def jinclaw_delete_memory(slug: str):
    store = MemoryStore()
    store.delete(slug)
    return {"code": 200, "msg": "记忆已删除"}


# ==================================================================
# Agent Chat (SSE)
# ==================================================================

@router.post("/ai/jinclaw/chat", summary="Jinclaw Agent SSE 流式对话")
async def jinclaw_chat_stream(
    chat_request: JinclawChatRequest,
    http_request: Request,
    user_id: Optional[int] = Depends(get_optional_user_id),
):
    remaining = _chat_access_fn(http_request, user_id)

    # Resolve workspace from task — try multiple fallbacks
    workspace_dir = None
    storage = JingentStorage()

    if chat_request.task_id:
        task = storage.get_task(chat_request.task_id, user_id=user_id)
        if task:
            project = storage.get_project(task.get("project_id", ""), user_id=user_id)
            if project and project.get("workspace_path"):
                workspace_dir = project.get("workspace_path")
                logger.info("[Jinclaw chat] workspace resolved: %s", workspace_dir)

    # Fallback: if no task or resolution failed, use most recent project's workspace
    if not workspace_dir:
        projects = storage.list_projects(user_id=user_id)
        if projects:
            workspace_dir = projects[0].get("workspace_path")
            logger.info("[Jinclaw chat] workspace fallback (first project): %s", workspace_dir)

    agent = AgentLoop(workspace_dir=workspace_dir)

    async def generate():
        try:
            async for event in agent.stream(
                user_message=chat_request.newMessage,
                history=[m.model_dump() for m in chat_request.history],
                user_id=user_id,
                lang=chat_request.lang,
            ):
                # Save to local storage if task is bound
                if chat_request.task_id:
                    try:
                        storage = JingentStorage()
                        storage.save_chat_line(chat_request.task_id, event)
                    except Exception:
                        logger.exception("Failed to save chat line for task %s", chat_request.task_id)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("Jinclaw agent stream crashed")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    headers = {}
    if remaining is not None:
        headers["X-Anon-Remaining"] = str(remaining)
        headers["Access-Control-Expose-Headers"] = "X-Anon-Remaining"
    return StreamingResponse(generate(), media_type="text/event-stream", headers=headers)


# ==================================================================
# Projects CRUD
# ==================================================================

@router.get("/ai/jinclaw/projects", summary="获取项目列表（按当前登录用户隔离）")
def jinclaw_projects(user_id: Optional[int] = Depends(get_optional_user_id)):
    storage = JingentStorage()
    projects = storage.list_projects(user_id=user_id)
    for p in projects:
        tasks = storage.list_tasks(p["id"], user_id=user_id)
        p["task_count"] = len(tasks)
        ws = p.get("workspace_path", "")
        if ws and ws != "_default_" and os.path.exists(ws):
            try:
                from jinclaw.system_prompt import _detect_project_context
                ctx = _detect_project_context(ws)
                p["context"] = {
                    "project_type": ctx.get("project_type", ""),
                    "languages": ctx.get("languages", []),
                    "frameworks": ctx.get("frameworks", []),
                }
            except Exception:
                logger.exception("Failed to detect project context for %s", ws)
    return {"code": 200, "projects": projects}


@router.post("/ai/jinclaw/projects", summary="创建项目（绑定工作文件夹 + 归属当前用户）")
def jinclaw_create_project(
    workspace_path: str = Query(...),
    name: str = Query(""),
    user_id: Optional[int] = Depends(get_optional_user_id),
):
    storage = JingentStorage()
    if not workspace_path or workspace_path == "_default_":
        appdata = Path(os.getenv("APPDATA", str(Path.home() / "AppData" / "Roaming")))
        base = appdata / "Jingent" / "ModularData" / "ai-agent" / "work-mode-projects"
        pid = _uuid.uuid4().hex[:24]
        workspace_path = str(base / pid)
        Path(workspace_path).mkdir(parents=True, exist_ok=True)
    if not name:
        name = Path(workspace_path).name or workspace_path
    project = storage.create_project(name, workspace_path, user_id=user_id)
    return {"code": 200, "project": project}


@router.delete("/ai/jinclaw/projects/{project_id}", summary="删除项目及所有任务（仅本人的）")
def jinclaw_delete_project(
    project_id: str,
    user_id: Optional[int] = Depends(get_optional_user_id),
):
    storage = JingentStorage()
    ok = storage.delete_project(project_id, user_id=user_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "项目不存在或无权删除"})
    return {"code": 200, "msg": "已删除"}


# ==================================================================
# Tasks CRUD
# ==================================================================

@router.get("/ai/jinclaw/tasks", summary="获取项目下的任务列表（按当前登录用户隔离）")
def jinclaw_tasks(
    project_id: str = Query(...),
    user_id: Optional[int] = Depends(get_optional_user_id),
):
    storage = JingentStorage()
    return {"code": 200, "project_id": project_id, "tasks": storage.list_tasks(project_id, user_id=user_id)}


@router.post("/ai/jinclaw/tasks", summary="在项目下创建任务（归属当前用户）")
def jinclaw_create_task(
    project_id: str = Query(...),
    name: str = Query("新任务"),
    user_id: Optional[int] = Depends(get_optional_user_id),
):
    storage = JingentStorage()
    try:
        task = storage.create_task(project_id, name, user_id=user_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": str(ve)})
    return {"code": 200, "task": task}


@router.delete("/ai/jinclaw/tasks/{task_id}", summary="删除任务（仅本人的）")
def jinclaw_delete_task(
    task_id: str,
    user_id: Optional[int] = Depends(get_optional_user_id),
):
    storage = JingentStorage()
    ok = storage.delete_task(task_id, user_id=user_id)
    return {"code": 200 if ok else 404, "msg": "已删除" if ok else "任务不存在或无权删除"}


@router.put("/ai/jinclaw/tasks/{task_id}/rename", summary="重命名任务（仅本人的）")
def jinclaw_rename_task(
    task_id: str,
    name: str = Query(...),
    user_id: Optional[int] = Depends(get_optional_user_id),
):
    storage = JingentStorage()
    storage.rename_task(task_id, name, user_id=user_id)
    return {"code": 200, "msg": "已重命名"}


@router.get("/ai/jinclaw/tasks/{task_id}/chat", summary="加载任务对话历史（仅本人 task 可读）")
def jinclaw_task_chat(
    task_id: str,
    user_id: Optional[int] = Depends(get_optional_user_id),
):
    storage = JingentStorage()
    events = storage.load_chat_history(task_id, user_id=user_id)
    return {"code": 200, "task_id": task_id, "events": events}


@router.post("/ai/jinclaw/tasks/{task_id}/chat/save", summary="保存一条聊天记录（仅本人 task 可写）")
def jinclaw_task_chat_save(
    task_id: str,
    req: JinclawSaveRequest,
    user_id: Optional[int] = Depends(get_optional_user_id),
):
    storage = JingentStorage()
    ok = storage.save_chat_line(task_id, {"type": req.type, "role": req.role, "message": req.message}, user_id=user_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "任务不存在或无权写入"})
    return {"code": 200, "msg": "已保存"}


# ==================================================================
# Workspace file browsing
# ==================================================================

@router.get("/ai/jinclaw/workspace/tree", summary="获取工作目录文件树（仅单级 depth，子节点需展开时再拉）")
def jinclaw_workspace_tree(path: str = Query("."), depth: int = Query(1), offset: int = Query(0), limit: int = Query(60)):
    root = Path(path).expanduser().resolve()
    if not root.exists():
        return {"code": 200, "tree": [], "total": 0, "note": f"目录尚为空或正在创建中: {path}"}

    SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
                 "target", ".idea", ".vscode", "dist", "build", ".jingent"}

    def walk(dir_path: Path, current_depth: int = 0) -> dict:
        if current_depth > depth:
            return {"items": [], "total": 0}
        try:
            with os.scandir(dir_path) as it:
                raw = list(it)
        except (PermissionError, OSError) as e:
            logger.warning("Scan failed %s: %s", dir_path, e)
            return {"items": [], "total": 0}

        # 先过滤：把需要 skip 的隐藏项/大依赖目录先踢掉再排序，避免对几百上千个无效条目排序
        filtered = []
        for entry in raw:
            name = entry.name
            if name.startswith('.') and name not in ('.env', '.gitignore'):
                continue
            if name in SKIP_DIRS:
                continue
            filtered.append(entry)
        # 过滤后再排序：(目录优先, 名称小写)
        filtered.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
        total = len(filtered)

        items = []
        end_idx = min(total, offset + limit)
        for idx in range(max(0, offset), end_idx):
            entry = filtered[idx]
            node = {
                "name": entry.name,
                "path": str(Path(entry.path)).replace("\\", "/"),
                "is_dir": entry.is_dir(),
            }
            if entry.is_dir():
                node["has_children"] = True
            items.append(node)

        if end_idx < total:
            items.append({
                "name": f"... (还有 {total - end_idx} 项，点击加载更多)",
                "is_dir": False,
                "path": str(dir_path).replace("\\", "/"),
                "_overflow": True,
                "_offset": end_idx,
                "_limit": limit,
                "_total": total,
            })
        return {"items": items, "total": total}

    result = walk(root)
    return {"code": 200, "path": str(root), "tree": result["items"], "total": result["total"]}


@router.get("/ai/jinclaw/workspace/read", summary="读取工作目录文件")
def jinclaw_workspace_read(path: str = Query(...), max_lines: int = Query(2000)):
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists():
        raise HTTPException(status_code=404, detail={"code": 404, "msg": f"文件不存在: {path}"})
    if not file_path.is_file():
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "路径不是文件"})

    size_mb = file_path.stat().st_size / (1024 * 1024)
    if size_mb > 10:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": f"文件过大 ({size_mb:.1f}MB)"})

    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            content = file_path.read_text(encoding="gbk")
        except Exception as e:
            logger.warning("Decode failed for %s, using replace mode: %s", file_path, e)
            content = file_path.read_text(encoding="utf-8", errors="replace")

    lines = content.split("\n")
    truncated = len(lines) > max_lines
    if truncated:
        content = "\n".join(lines[:max_lines]) + f"\n... (共 {len(lines)} 行，仅显示前 {max_lines} 行)"

    ext = file_path.suffix.lower()
    lang_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript", ".rs": "rust",
        ".html": "html", ".css": "css", ".json": "json", ".md": "markdown",
        ".toml": "toml", ".yaml": "yaml", ".yml": "yaml", ".sql": "sql",
        ".sh": "shell", ".bat": "bat", ".ps1": "powershell",
        ".java": "java", ".go": "go", ".cpp": "cpp", ".c": "c",
        ".h": "c", ".hpp": "cpp", ".cs": "csharp", ".rb": "ruby",
    }
    language = lang_map.get(ext, "plaintext")

    return {
        "code": 200,
        "path": str(file_path),
        "content": content,
        "language": language,
        "total_lines": len(lines),
    }


@router.post("/ai/jinclaw/workspace/fs_action", summary="文件/文件夹操作：在资源管理器中显示 / 重命名 / 删除")
def jinclaw_workspace_fs_action(req: WorkspaceFsActionRequest):
    import shutil
    target = Path(req.path).expanduser().resolve()
    if not target.exists() and req.action != "rename":
        raise HTTPException(status_code=404, detail={"code": 404, "msg": f"路径不存在: {req.path}"})

    if req.action == "explore":
        # 在文件资源管理器中显示（选中目标）
        try:
            if os.name == "nt":
                # Windows: explorer /select,"path"
                subprocess.Popen(["explorer", "/select,", str(target)])
            elif _is_mac():
                subprocess.Popen(["open", "-R", str(target)])
            else:
                # Linux: 有 xdg-open 就打开父目录，否则失败提示
                parent = str(target.parent)
                if shutil.which("xdg-open"):
                    subprocess.Popen(["xdg-open", parent])
                else:
                    raise HTTPException(status_code=400, detail={"code": 400, "msg": "未检测到文件管理器 (xdg-open)"})
            return {"code": 200, "msg": "ok"}
        except HTTPException:
            raise
        except Exception as e:
            logger.warning("explore failed %s: %s", target, e)
            raise HTTPException(status_code=500, detail={"code": 500, "msg": f"无法打开: {e}"})

    elif req.action == "rename":
        if not req.new_name:
            raise HTTPException(status_code=400, detail={"code": 400, "msg": "缺少 new_name"})
        if "/" in req.new_name or "\\" in req.new_name:
            raise HTTPException(status_code=400, detail={"code": 400, "msg": "new_name 不能包含路径分隔符"})
        if not target.exists():
            raise HTTPException(status_code=404, detail={"code": 404, "msg": f"路径不存在: {req.path}"})
        new_path = target.parent / req.new_name
        if new_path.exists():
            raise HTTPException(status_code=409, detail={"code": 409, "msg": f"同名文件/文件夹已存在: {req.new_name}"})
        try:
            target.rename(new_path)
            return {"code": 200, "msg": "ok", "new_path": str(new_path).replace("\\", "/")}
        except Exception as e:
            logger.warning("rename failed %s -> %s: %s", target, new_path, e)
            raise HTTPException(status_code=500, detail={"code": 500, "msg": f"重命名失败: {e}"})

    elif req.action == "delete":
        try:
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            return {"code": 200, "msg": "ok"}
        except Exception as e:
            logger.warning("delete failed %s: %s", target, e)
            raise HTTPException(status_code=500, detail={"code": 500, "msg": f"删除失败: {e}"})

    else:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": f"未知 action: {req.action}"})


def _is_mac() -> bool:
    import sys
    return sys.platform == "darwin"


# ==================================================================
# Diff management
# ==================================================================

def _apply_unified_diff(original: str, patch: str) -> str:
    """Apply a unified diff patch to original content (kept here for diff routes)."""
    original_lines = original.split("\n")
    result_lines: list = []
    orig_idx = 0
    in_hunk = False

    for line in patch.split("\n"):
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("@@"):
            in_hunk = True
            parts = line.split()
            if len(parts) >= 2:
                range_str = parts[1].lstrip("-")
                if "," in range_str:
                    hunk_start = int(range_str.split(",")[0]) - 1
                else:
                    hunk_start = int(range_str) - 1
                while orig_idx < hunk_start and orig_idx < len(original_lines):
                    result_lines.append(original_lines[orig_idx])
                    orig_idx += 1
            continue

        if in_hunk:
            if line.startswith("+") and not line.startswith("++"):
                result_lines.append(line[1:])
            elif line.startswith("-") and not line.startswith("--"):
                orig_idx += 1
            elif line.startswith(" "):
                result_lines.append(line[1:])
                orig_idx += 1

    while orig_idx < len(original_lines):
        result_lines.append(original_lines[orig_idx])
        orig_idx += 1

    return "\n".join(result_lines)


def _apply_unified_diff_reverse(patched: str, patch: str) -> str:
    reversed_lines = []
    for line in patch.split("\n"):
        if line.startswith("+") and not line.startswith("++"):
            reversed_lines.append("-" + line[1:])
        elif line.startswith("-") and not line.startswith("--"):
            reversed_lines.append("+" + line[1:])
        else:
            reversed_lines.append(line)
    return _apply_unified_diff(patched, "\n".join(reversed_lines))


@router.post("/ai/jinclaw/diffs", summary="保存 diff")
def jinclaw_save_diff(req: DiffSaveRequest):
    storage = JingentStorage()
    diff_id = storage.save_diff(req.task_id, req.file_path, req.patch)
    return {"code": 200, "diff_id": diff_id}


@router.get("/ai/jinclaw/diffs", summary="获取任务的所有 diff")
def jinclaw_list_diffs(task_id: str = Query(...)):
    storage = JingentStorage()
    return {"code": 200, "diffs": storage.list_diffs(task_id)}


@router.post("/ai/jinclaw/diffs/{diff_id}/apply", summary="应用 diff 到文件")
def jinclaw_apply_diff(diff_id: str):
    storage = JingentStorage()
    diff = storage.get_diff(diff_id)
    if not diff:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "Diff 不存在"})

    file_path = Path(diff["file_path"]).expanduser().resolve()
    patch = diff["patch"]

    try:
        original = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
        patched = _apply_unified_diff(original, patch)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(patched, encoding="utf-8")
        storage.mark_diff_applied(diff_id, True)
        logger.info("Diff %s applied to %s", diff_id, file_path)
        return {"code": 200, "msg": f"已应用修改到 {file_path}"}
    except Exception as e:
        logger.exception("Apply diff %s failed", diff_id)
        raise HTTPException(status_code=500, detail={"code": 500, "msg": f"应用失败: {str(e)}"})


@router.post("/ai/jinclaw/diffs/{diff_id}/revert", summary="撤销 diff")
def jinclaw_revert_diff(diff_id: str):
    storage = JingentStorage()
    diff = storage.get_diff(diff_id)
    if not diff:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "Diff 不存在"})
    if not diff.get("applied"):
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "Diff 尚未应用"})

    file_path = Path(diff["file_path"]).expanduser().resolve()
    patch = diff["patch"]

    try:
        patched = file_path.read_text(encoding="utf-8")
        original = _apply_unified_diff_reverse(patched, patch)
        file_path.write_text(original, encoding="utf-8")
        storage.mark_diff_applied(diff_id, False)
        logger.info("Diff %s reverted on %s", diff_id, file_path)
        return {"code": 200, "msg": f"已撤销 {file_path} 的修改"}
    except Exception as e:
        logger.exception("Revert diff %s failed", diff_id)
        raise HTTPException(status_code=500, detail={"code": 500, "msg": f"撤销失败: {str(e)}"})


# ==================================================================
# Shell execution
# ==================================================================

@router.get("/ai/jinclaw/shell", summary="执行 Shell/PowerShell 命令")
def jinclaw_shell_exec(
    command: str = Query(...),
    cwd: str = Query("."),
    timeout: int = Query(30),
    shell_type: str = Query("powershell"),
):
    cmd_lower = command.lower().strip()
    forbidden = ["format", "shutdown", "restart", "taskkill /f /im explorer",
                 "del /s /q c:", "rm -rf /", "rd /s /q c:", "Remove-Item -Path C:\\"]
    for fw in forbidden:
        if fw in cmd_lower:
            raise HTTPException(status_code=400, detail={"code": 400, "msg": f"禁止执行危险命令"})

    try:
        if shell_type == "powershell":
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                cwd=cwd, capture_output=True, text=True,
                timeout=timeout, encoding="utf-8", errors="replace",
            )
        else:
            result = subprocess.run(
                command, shell=True, cwd=cwd,
                capture_output=True, text=True,
                timeout=timeout, encoding="utf-8", errors="replace",
            )
        logger.info("Shell [%s] exit=%s (cwd=%s)", shell_type, result.returncode, cwd)
        return {
            "code": 200,
            "exit_code": result.returncode,
            "stdout": result.stdout[:10000],
            "stderr": result.stderr[:5000],
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail={"code": 408, "msg": f"命令超时 ({timeout}s)"})
    except Exception as e:
        logger.exception("Shell execution failed")
        raise HTTPException(status_code=500, detail={"code": 500, "msg": str(e)})
