"""
Jingent AI — 资源与数据路径助手。

新目录结构约定（网页端）：
    项目根/
    ├── backend/            # 后端代码（main.py + app/ + tests/ + .env 等）
    │   ├── main.py
    │   ├── app/
    │   ├── tests/
    │   ├── .env / .env.example
    │   └── requirements.txt / pyproject.toml
    ├── front/              # 前端资源
    │   ├── static/
    │   └── templates/
    ├── ops/                # 运维运行时数据
    │   ├── logs/           # 日志
    │   ├── temp/           # 临时文件
    │   ├── uploads/        # 前端上传的第三方资源
    │   └── data/           # 技能包等三方资源
    └── deploy/ docs/ 等

路径定位原则：一切以本文件（backend/app/core/paths.py）为锚点推导，
不依赖调用方的 cwd，保证从任意目录启动、任意 CWD 下都稳定。
"""
import os
import sys
from pathlib import Path

# backend/ 目录 = 本文件往上三级（app/core/paths.py -> app/core -> app -> backend）
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

# 项目根目录 = backend/ 的上一级
_PROJECT_ROOT = _BACKEND_DIR.parent

# ops/ 运维数据目录（日志/上传/三方资源/临时）
_OPS_DIR = _PROJECT_ROOT / "ops"

# front/ 前端资源目录（static + templates）
_FRONT_DIR = _PROJECT_ROOT / "front"


def backend_dir() -> Path:
    """backend/ 目录（后端代码根）。"""
    return _BACKEND_DIR


def project_root() -> Path:
    """项目根目录。"""
    return _PROJECT_ROOT


def resource_path(rel: str = "") -> Path:
    """
    前端只读资源路径：front/{rel}（templates/static 已移入 front/）。
    保留 _MEIPASS 兼容：PyInstaller 打包场景读临时目录（当前网页端暂不用）。
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / rel
    return _FRONT_DIR / rel


def ops_dir() -> Path:
    """ops/ 运维数据根目录。"""
    return _OPS_DIR


def data_dir() -> Path:
    """三方资源目录 ops/data/（技能包等）。自动创建。"""
    d = _OPS_DIR / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def uploads_dir() -> Path:
    """前端上传目录 ops/uploads/。自动创建。"""
    d = _OPS_DIR / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def logs_dir() -> Path:
    """日志目录 ops/logs/。自动创建。"""
    d = _OPS_DIR / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def temp_dir() -> Path:
    """临时文件目录 ops/temp/。自动创建。"""
    d = _OPS_DIR / "temp"
    d.mkdir(parents=True, exist_ok=True)
    return d


def env_file() -> Path:
    """后端 .env 路径（backend/.env）。"""
    return _BACKEND_DIR / ".env"


def env_example_file() -> Path:
    """后端 .env.example 路径（backend/.env.example）。"""
    return _BACKEND_DIR / ".env.example"


def db_file() -> Path:
    """默认 SQLite 数据库文件路径（backend/app.db）。"""
    return _BACKEND_DIR / "app.db"


def ensure_env_file() -> Path:
    """
    首次运行：若 backend/.env 不存在，从 backend/.env.example 复制一份，
    并为本机生成一个独立的随机 SECRET_KEY。

    每台机器一个独立密钥很重要：如果所有安装共用同一个占位符密钥，
    任何人都能用自己那份密钥伪造出在别人机器上有效的 JWT。
    """
    target = env_file()
    if target.exists():
        return target

    example = env_example_file()
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
