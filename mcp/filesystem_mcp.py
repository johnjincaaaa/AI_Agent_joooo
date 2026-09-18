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
        description=(
            "创建新文件，或整体重写一个文件。"
            "⚠️ 只在新建文件、或确实要替换整个文件内容时用。"
            "修改已有文件的局部内容，一律优先用 mcp_file_edit —— 整体重写大文件既慢又容易改坏无关代码。"
        ),
        parameters={"path": "文件路径", "content": "要写入的内容", "encoding": "编码格式，默认 utf-8"},
    )

    manager.register_tool(
        name="mcp_file_edit",
        func=file_edit,
        description=(
            "精确替换文件里的一段文本（局部修改已有文件的首选方式）。"
            "old_string 必须在文件中唯一匹配：如果匹配到 0 处或多处都会报错，"
            "此时请带上更多上下文（前后多几行）让它唯一，再重试。"
            "要替换多处相同文本时，显式传 expected_count 说明预期处数。"
            "返回统一 diff，能直接看出改了什么。"
        ),
        parameters={
            "path": "文件路径",
            "old_string": "要被替换的原文（必须唯一匹配，需带足够上下文）",
            "new_string": "替换后的新文本（传空字符串表示删除这段）",
            "expected_count": "预期匹配处数，默认 1；要批量替换多处时显式指定",
            "encoding": "编码格式，默认 utf-8",
        },
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


# 超过这个大小就不算 diff（difflib 在大文件上很慢）
MAX_DIFF_BYTES = 1024 * 1024


def make_unified_diff(old: str, new: str, path: str) -> str:
    """生成统一 diff 文本。内容过大时退化为只报告行数变化。"""
    import difflib

    if len(old) > MAX_DIFF_BYTES or len(new) > MAX_DIFF_BYTES:
        delta = len(new.splitlines()) - len(old.splitlines())
        return f"(文件过大，跳过 diff 计算；行数变化 {delta:+d})"

    diff = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        n=3,
    )
    return "".join(diff)


def file_edit(
    path: str,
    old_string: str,
    new_string: str = "",
    expected_count: int = 1,
    encoding: str = "utf-8",
) -> str:
    """
    精确替换文件中的一段文本。

    要求 old_string 唯一匹配（或匹配数等于 expected_count），
    否则报错并说明实际匹配了多少处 —— 让模型知道要补上下文而不是盲目重试。
    """
    try:
        file_path = Path(path).expanduser().resolve()

        if not file_path.exists():
            return f"错误：文件不存在 - {path}\n如果是要新建文件，请用 mcp_file_write。"
        if not file_path.is_file():
            return f"错误：路径不是文件 - {path}"

        safe_check = _check_safe_path(file_path)
        if safe_check:
            return safe_check

        if not old_string:
            return "错误：old_string 不能为空。要整体重写文件请用 mcp_file_write。"

        # 读文件（编码回退和 file_read 保持一致）
        content = None
        used_encoding = encoding
        for enc in [encoding, "utf-8", "utf-8-sig", "gbk", "gb2312"]:
            try:
                content = file_path.read_text(encoding=enc)
                used_encoding = enc
                break
            except UnicodeDecodeError:
                continue
        if content is None:
            return f"错误：无法以支持的编码读取文件 {path}"

        actual = content.count(old_string)

        if actual == 0:
            preview = old_string[:120].replace("\n", "\\n")
            return (
                f"错误：在 {path} 中找不到 old_string（匹配 0 处）。\n"
                f"要找的内容开头：{preview}\n"
                "常见原因：缩进/空格不一致、内容与文件实际不符。"
                "建议先用 mcp_file_read 确认原文，再照抄过来。"
            )

        try:
            want = int(expected_count)
        except (TypeError, ValueError):
            want = 1

        if actual != want:
            return (
                f"错误：old_string 在 {path} 中匹配了 {actual} 处，但预期 {want} 处。\n"
                f"请在 old_string 里带上更多上下文（前后多几行）让它唯一；"
                f"如果确实要替换全部 {actual} 处，请传 expected_count={actual}。"
            )

        new_content = content.replace(old_string, new_string)

        if new_content == content:
            return f"提示：替换后内容无变化（old_string 与 new_string 相同），未写入 {path}。"

        file_path.write_text(new_content, encoding=used_encoding)

        diff = make_unified_diff(content, new_content, file_path.name)
        added = sum(1 for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in diff.splitlines() if l.startswith("-") and not l.startswith("---"))

        return (
            f"成功：已修改 {file_path}（替换 {actual} 处，+{added} -{removed} 行）\n\n{diff}"
        )
    except Exception as e:
        return f"编辑文件失败: {str(e)}"


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
