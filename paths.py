"""
Jingent AI — resource & data path helpers.

Two kinds of paths:
- resource_path(): 只读资源（templates/static/AGENTS.md/.env.example）。
  PyInstaller 打包后从 sys._MEIPASS 临时目录读，开发时从项目根目录读。
- data_dir(): 可写数据（SQLite DB / .env / uploads / logs）。
  统一放到 %APPDATA%/Jingent/，安装到 Program Files 也可写。
"""
import os
import sys
from pathlib import Path

# 项目根目录（源码运行时），用于 dev 模式定位资源
_PROJECT_ROOT = Path(__file__).resolve().parent


def resource_path(rel: str = "") -> Path:
    """只读资源路径。打包后从 _MEIPASS 读，开发时从项目根读。"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / rel
    return _PROJECT_ROOT / rel


def data_dir() -> Path:
    """可写数据目录 %APPDATA%/Jingent/（自动创建）。"""
    base = Path(os.getenv("APPDATA", str(Path.home()))) / "Jingent"
    base.mkdir(parents=True, exist_ok=True)
    return base


def env_file() -> Path:
    """运行时 .env 文件路径（用户 API key 等）。"""
    return data_dir() / ".env"


def ensure_env_file() -> Path:
    """
    首次运行：若 data_dir/.env 不存在，从 .env.example 复制一份，
    并为本机生成一个独立的随机 SECRET_KEY。

    每台机器一个独立密钥很重要：如果所有安装共用同一个占位符密钥，
    任何人都能用自己那份密钥伪造出在别人机器上有效的 JWT。
    """
    target = env_file()
    if target.exists():
        return target

    example = resource_path(".env.example")
    content = example.read_text(encoding="utf-8") if example.exists() else ""

    # 为本机注入随机密钥（.env.example 里 SECRET_KEY 是留空的）
    if not _has_secret_key(content):
        content = _inject_secret_key(content)

    target.write_text(content, encoding="utf-8")
    return target


def _has_secret_key(content: str) -> bool:
    """检查 .env 文本里 SECRET_KEY 是否已有非空值。"""
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("SECRET_KEY=") and line[len("SECRET_KEY="):].strip():
            return True
    return False


def _inject_secret_key(content: str) -> str:
    """把随机密钥写进 SECRET_KEY= 行（没有该行则追加）。"""
    import secrets

    key = secrets.token_urlsafe(32)
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("SECRET_KEY="):
            lines[i] = f"SECRET_KEY={key}"
            return "\n".join(lines) + "\n"
    lines.append(f"SECRET_KEY={key}")
    return "\n".join(lines) + "\n"
