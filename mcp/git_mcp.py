"""
Git MCP：本地 Git 仓库操作工具
包含：status、pull、push、commit、branch、merge、log 等
"""
import subprocess
import os
from pathlib import Path
from typing import Optional


def register_git_tools(manager):
    """注册 Git 相关工具。"""

    manager.register_tool(
        name="mcp_git_status",
        func=git_status,
        description="查看 Git 仓库当前状态（修改的文件、暂存区等）。",
        parameters={"path": "仓库路径，默认当前目录"},
    )

    manager.register_tool(
        name="mcp_git_pull",
        func=git_pull,
        description="从远程仓库拉取最新代码。",
        parameters={"path": "仓库路径", "remote": "远程仓库名，默认 origin", "branch": "分支名，默认当前分支"},
    )

    manager.register_tool(
        name="mcp_git_push",
        func=git_push,
        description="推送本地提交到远程仓库。",
        parameters={"path": "仓库路径", "remote": "远程仓库名，默认 origin", "branch": "分支名，默认当前分支"},
    )

    manager.register_tool(
        name="mcp_git_commit",
        func=git_commit,
        description="提交修改到本地仓库。会自动 add 所有修改的文件。",
        parameters={"path": "仓库路径", "message": "提交信息"},
    )

    manager.register_tool(
        name="mcp_git_branch",
        func=git_branch,
        description="查看或创建分支。",
        parameters={"path": "仓库路径", "action": "操作：list/create/delete，默认 list", "name": "分支名（创建/删除时）"},
    )

    manager.register_tool(
        name="mcp_git_log",
        func=git_log,
        description="查看提交历史。",
        parameters={"path": "仓库路径", "limit": "显示条数，默认 10"},
    )


def _run_git(args: list, path: str = ".") -> subprocess.CompletedProcess:
    """执行 Git 命令。"""
    repo_path = Path(path).expanduser().resolve()
    return subprocess.run(
        ["git"] + args,
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        timeout=60,
        encoding="utf-8",
        errors="replace",
    )


def git_status(path: str = ".") -> str:
    """查看 Git 状态。"""
    try:
        result = _run_git(["status"], path)
        if result.returncode != 0:
            return f"错误：{result.stderr.strip() or 'Git 命令执行失败'}"
        return result.stdout.strip() or "工作区干净，没有修改。"
    except Exception as e:
        return f"Git 状态查询失败: {str(e)}"


def git_pull(path: str = ".", remote: str = "origin", branch: str = "") -> str:
    """拉取远程代码。"""
    try:
        args = ["pull"]
        if remote:
            args.append(remote)
        if branch:
            args.append(branch)
        result = _run_git(args, path)
        if result.returncode != 0:
            return f"Pull 失败：{result.stderr.strip()}"
        return f"Pull 成功：\n{result.stdout.strip()}"
    except Exception as e:
        return f"Git pull 失败: {str(e)}"


def git_push(path: str = ".", remote: str = "origin", branch: str = "") -> str:
    """推送代码到远程。"""
    try:
        args = ["push"]
        if remote:
            args.append(remote)
        if branch:
            args.append(branch)
        result = _run_git(args, path)
        if result.returncode != 0:
            return f"Push 失败：{result.stderr.strip()}"
        return f"Push 成功：\n{result.stdout.strip()}"
    except Exception as e:
        return f"Git push 失败: {str(e)}"


def git_commit(path: str = ".", message: str = "") -> str:
    """提交修改。"""
    try:
        if not message.strip():
            return "错误：请提供提交信息"

        # 先 add 所有修改
        result_add = _run_git(["add", "-A"], path)
        if result_add.returncode != 0:
            return f"Add 失败：{result_add.stderr.strip()}"

        result = _run_git(["commit", "-m", message], path)
        if result.returncode != 0:
            return f"Commit 失败：{result.stderr.strip()}"
        return f"Commit 成功：\n{result.stdout.strip()}"
    except Exception as e:
        return f"Git commit 失败: {str(e)}"


def git_branch(path: str = ".", action: str = "list", name: str = "") -> str:
    """分支操作。"""
    try:
        if action == "list":
            result = _run_git(["branch", "-a"], path)
            if result.returncode != 0:
                return f"错误：{result.stderr.strip()}"
            return result.stdout.strip()
        elif action == "create":
            if not name:
                return "错误：请提供分支名"
            result = _run_git(["checkout", "-b", name], path)
            if result.returncode != 0:
                return f"创建分支失败：{result.stderr.strip()}"
            return f"分支 {name} 创建成功"
        elif action == "delete":
            if not name:
                return "错误：请提供分支名"
            result = _run_git(["branch", "-d", name], path)
            if result.returncode != 0:
                return f"删除分支失败：{result.stderr.strip()}"
            return f"分支 {name} 删除成功"
        else:
            return f"错误：未知的分支操作 - {action}"
    except Exception as e:
        return f"Git branch 操作失败: {str(e)}"


def git_log(path: str = ".", limit: int = 10) -> str:
    """查看提交历史。"""
    try:
        result = _run_git([
            "log",
            f"-{limit}",
            "--oneline",
            "--graph",
            "--decorate",
            "--all",
        ], path)
        if result.returncode != 0:
            return f"错误：{result.stderr.strip()}"
        return result.stdout.strip() or "没有提交历史。"
    except Exception as e:
        return f"Git log 查询失败: {str(e)}"
