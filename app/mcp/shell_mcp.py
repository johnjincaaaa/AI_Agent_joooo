"""
Shell MCP：本地命令执行工具
包含：CMD/PowerShell 命令执行、进程管理等
"""
import subprocess
import os
from typing import Optional


def register_shell_tools(manager):
    """注册 Shell 相关工具。"""

    manager.register_tool(
        name="mcp_shell_exec",
        func=shell_exec,
        description="执行本地 Shell 命令（Windows CMD / PowerShell）。返回命令的标准输出和错误输出。",
        parameters={
            "command": "要执行的命令",
            "timeout": "超时时间（秒），默认 30",
            "shell_type": "命令类型：cmd / powershell，默认 cmd",
        },
    )

    manager.register_tool(
        name="mcp_shell_background",
        func=shell_background,
        description="在后台启动一个进程，不阻塞等待。返回进程 ID。",
        parameters={
            "command": "要执行的命令",
            "shell_type": "命令类型：cmd / powershell，默认 cmd",
        },
    )


def shell_exec(command: str, timeout: int = 30, shell_type: str = "cmd") -> str:
    """执行 Shell 命令并返回结果。"""
    try:
        if not command.strip():
            return "错误：命令不能为空"

        # 安全检查：不允许执行危险命令
        danger_check = _check_dangerous_command(command)
        if danger_check:
            return danger_check

        if shell_type.lower() == "powershell":
            cmd = ["powershell", "-NoProfile", "-Command", command]
        else:
            cmd = ["cmd", "/C", command]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )

        output = f"===== 执行命令: {command} =====\n"
        output += f"退出码: {result.returncode}\n"

        if result.stdout:
            stdout = result.stdout
            if len(stdout) > 10000:
                stdout = stdout[:10000] + "\n...(输出过长，已截断)"
            output += f"\n----- 标准输出 -----\n{stdout}"

        if result.stderr:
            stderr = result.stderr
            if len(stderr) > 5000:
                stderr = stderr[:5000] + "\n...(错误输出过长，已截断)"
            output += f"\n----- 错误输出 -----\n{stderr}"

        return output.strip()

    except subprocess.TimeoutExpired:
        return f"错误：命令执行超时（{timeout}秒）- {command}"
    except Exception as e:
        return f"执行命令失败: {str(e)}"


def shell_background(command: str, shell_type: str = "cmd") -> str:
    """在后台启动进程。"""
    try:
        if not command.strip():
            return "错误：命令不能为空"

        danger_check = _check_dangerous_command(command)
        if danger_check:
            return danger_check

        if shell_type.lower() == "powershell":
            cmd = ["powershell", "-NoProfile", "-Command", command]
        else:
            cmd = ["cmd", "/C", command]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        return f"成功：后台进程已启动，PID: {process.pid}\n命令: {command}"

    except Exception as e:
        return f"启动后台进程失败: {str(e)}"


def _check_dangerous_command(command: str) -> Optional[str]:
    """检查是否为危险命令。"""
    cmd_lower = command.lower().strip()

    # 绝对禁止的命令
    forbidden = [
        "format", "del /s", "deltree", "rmdir /s",
        "shutdown", "restart", "taskkill /f /im explorer",
    ]

    for fw in forbidden:
        if fw in cmd_lower:
            return f"错误：禁止执行危险命令 - {command}"

    # 警告但允许执行的命令
    warnings = [
        ("rm -rf", "此命令会递归删除文件，请确认路径正确"),
        ("del ", "此命令会删除文件，请确认路径正确"),
        ("rd /s", "此命令会删除目录，请确认路径正确"),
    ]

    for pattern, msg in warnings:
        if pattern in cmd_lower:
            # 在输出中添加警告但继续执行
            return None  # 暂时直接允许，后续可以加确认机制

    return None
