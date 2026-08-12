"""
FileSystem MCP：本地文件系统操作工具
包含：读取文件、写入文件、遍历目录、文件统计等
"""
import os
import shutil
from pathlib import Path
from typing import Optional


def register_filesystem_tools(manager):
    """注册文件系统相关工具。"""

    manager.register_tool(
        name="mcp_file_read",
        func=file_read,
        description="读取本地文件内容。支持 TXT、MD、JSON、CSV 等文本文件。",
        parameters={"path": "文件路径（绝对或相对）", "encoding": "编码格式，默认 utf-8"},
    )

    manager.register_tool(
        name="mcp_file_write",
        func=file_write,
        description="创建或写入本地文件。如果文件已存在会被覆盖。",
        parameters={"path": "文件路径", "content": "要写入的内容", "encoding": "编码格式，默认 utf-8"},
    )

    manager.register_tool(
        name="mcp_file_list",
        func=file_list,
        description="列出目录下的所有文件和子目录。",
        parameters={"path": "目录路径", "recursive": "是否递归遍历子目录，默认 false"},
    )

    manager.register_tool(
        name="mcp_file_stat",
        func=file_stat,
        description="获取文件或目录的详细信息（大小、修改时间等）。",
        parameters={"path": "文件或目录路径"},
    )


def file_read(path: str, encoding: str = "utf-8") -> str:
    """读取本地文件内容。"""
    try:
        file_path = Path(path).expanduser().resolve()
        if not file_path.exists():
            return f"错误：文件不存在 - {path}"
        if not file_path.is_file():
            return f"错误：路径不是文件 - {path}"

        # 按大小限制读取
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > 10:
            return f"错误：文件过大（{size_mb:.1f}MB），请使用更小的文件"

        # 尝试多种编码
        for enc in [encoding, "utf-8", "utf-8-sig", "gbk", "gb2312"]:
            try:
                content = file_path.read_text(encoding=enc)
                truncated = len(content) > 50000
                if truncated:
                    content = content[:50000] + "\n\n...(内容过长，已截断)"
                return f"===== 文件: {file_path} =====\n大小: {file_path.stat().st_size} 字节\n编码: {enc}\n\n{content}"
            except UnicodeDecodeError:
                continue

        return f"错误：无法以支持的编码读取文件 {path}"
    except Exception as e:
        return f"读取文件失败: {str(e)}"


def file_write(path: str, content: str, encoding: str = "utf-8") -> str:
    """写入或创建本地文件。"""
    try:
        file_path = Path(path).expanduser().resolve()

        # 安全检查：不允许写入系统关键目录
        safe_check = _check_safe_path(file_path)
        if safe_check:
            return safe_check

        # 创建父目录
        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_path.write_text(content, encoding=encoding)
        return f"成功：文件已写入 {file_path}（{len(content)} 字符）"
    except Exception as e:
        return f"写入文件失败: {str(e)}"


def file_list(path: str = ".", recursive: bool = False) -> str:
    """列出目录下的文件和子目录。"""
    try:
        dir_path = Path(path).expanduser().resolve()
        if not dir_path.exists():
            return f"错误：目录不存在 - {path}"
        if not dir_path.is_dir():
            return f"错误：路径不是目录 - {path}"

        files = []
        if recursive:
            for item in sorted(dir_path.rglob("*")):
                if len(files) >= 500:
                    files.append("...(结果过多，已截断)")
                    break
                rel = item.relative_to(dir_path)
                files.append(f"{'📁' if item.is_dir() else '📄'} {rel}")
        else:
            for item in sorted(dir_path.iterdir()):
                if len(files) >= 200:
                    files.append("...(结果过多，已截断)")
                    break
                files.append(f"{'📁' if item.is_dir() else '📄'} {item.name}  {item.stat().st_size if item.is_file() else ''}")

        return f"===== 目录: {dir_path} =====\n共 {len(files)} 项\n\n" + "\n".join(files)
    except Exception as e:
        return f"遍历目录失败: {str(e)}"


def file_stat(path: str) -> str:
    """获取文件或目录的详细信息。"""
    try:
        file_path = Path(path).expanduser().resolve()
        if not file_path.exists():
            return f"错误：路径不存在 - {path}"

        stat = file_path.stat()
        import datetime
        info = [
            f"路径: {file_path}",
            f"类型: {'目录' if file_path.is_dir() else '文件'}",
            f"大小: {stat.st_size} 字节 ({stat.st_size / 1024:.1f} KB)",
            f"创建时间: {datetime.datetime.fromtimestamp(stat.st_ctime)}",
            f"修改时间: {datetime.datetime.fromtimestamp(stat.st_mtime)}",
            f"访问时间: {datetime.datetime.fromtimestamp(stat.st_atime)}",
        ]
        return "\n".join(info)
    except Exception as e:
        return f"获取文件信息失败: {str(e)}"


def _check_safe_path(file_path: Path) -> Optional[str]:
    """安全检查：防止写入系统关键目录。"""
    home = Path.home()
    dangerous_paths = [
        Path("/"), Path("C:/"), Path("D:/Windows"), Path("C:/Windows"),
        Path("C:/Program Files"), Path("C:/Program Files (x86)"),
    ]
    for dp in dangerous_paths:
        try:
            if file_path == dp or str(file_path).startswith(str(dp) + os.sep):
                return f"错误：不允许写入系统目录 {file_path}"
        except Exception:
            continue
    return None
