"""
Jingent AI 运行时配置（从 .env 加载）与启动校验。

只负责「环境相关、因部署而异的配置」：
  - JWT / LLM / 限流 / 后台管理员 / 数据库连接
  - validate_config()：启动时提前暴露缺配置/错配置

业务数据（场景预设、上传白名单等）不在本模块，见：
  - app/config/scenes.py
  - app/config/constants.py
"""
import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv

from app.core.paths import ensure_env_file, db_file, env_file

# 运行配置从 backend/.env 加载；缺失时回退到自动生成的 .env
# override=True：让 .env 文件的值优先于外部残留的环境变量（避免 shell 里的
# 旧 SQLALCHEMY_DATABASE_URL 等污染配置）
load_dotenv(env_file() if env_file().exists() else ensure_env_file(), override=True)


class ConfigError(RuntimeError):
    """Raised when required config values are missing or invalid."""


# ==================================================================
# JWT
# ==================================================================
SECRET_KEY = os.getenv("SECRET_KEY", "")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# ==================================================================
# AI / LLM (OpenAI-compatible)
# ==================================================================
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")

MODEL = os.getenv("LLM_MODEL") or os.getenv("MODEL", "deepseek-chat")
LLM_MODEL = MODEL
LLM_BASE_URL = (
    os.getenv("LLM_BASE_URL")
    or os.getenv("DASHSCOPE_URL", "https://api.deepseek.com/v1")
)
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")

# Compatibility aliases（旧代码用 DASHSCOPE_* 命名）
DASHSCOPE_URL = LLM_BASE_URL
DASHSCOPE_API_KEY = LLM_API_KEY

# ==================================================================
# Embedding / 向量模型（RAG 主对话历史语义检索用）
# ==================================================================
# 默认走本地 Ollama 的 bge-m3（免费、中文友好、隐私不外发）。
# 也可配置为 OpenAI 兼容的 embedding 服务（带 /v1 的地址 + API Key）。
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

# ==================================================================
# Rate limiting (anonymous users)
# ==================================================================
ANONYMOUS_RATE_LIMIT_MAX = int(os.getenv("ANONYMOUS_RATE_LIMIT_MAX", "10"))

# ==================================================================
# Admin
# ==================================================================
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# ==================================================================
# Database
# ==================================================================
SQLALCHEMY_DATABASE_URL = os.getenv(
    "SQLALCHEMY_DATABASE_URL",
    f"sqlite:///{db_file()}",
)


# ==================================================================
# Validation — MUST call at startup
# ==================================================================

@dataclass
class ValidationWarning:
    level: str       # "WARN" or "FATAL"
    field: str
    message: str


def validate_config(strict: bool = True) -> List[ValidationWarning]:
    """
    Check required and important config values.

    In strict mode (default), FATAL warnings raise ConfigError so the
    app refuses to start. Non-strict mode returns all warnings for
    the caller to decide (useful in tests / desktop mode).
    """
    warnings: List[ValidationWarning] = []

    # ── JWT ─────────────────────────────────────────────
    if not SECRET_KEY:
        warnings.append(ValidationWarning(
            "FATAL", "SECRET_KEY",
            "未配置 SECRET_KEY。JWT 登录将无法工作，请在 .env 中设置：SECRET_KEY=你的随机密钥"
        ))

    # ── LLM API ─────────────────────────────────────────
    if not LLM_API_KEY:
        warnings.append(ValidationWarning(
            "WARN", "LLM_API_KEY",
            "未配置 LLM_API_KEY，AI 对话接口可能返回 401 错误。桌面端可容忍，部署版必须设置。"
        ))
    if not LLM_BASE_URL:
        warnings.append(ValidationWarning(
            "FATAL", "LLM_BASE_URL",
            "LLM_BASE_URL 为空，AI 对话无法工作。"
        ))
    if not LLM_MODEL:
        warnings.append(ValidationWarning(
            "FATAL", "LLM_MODEL",
            "LLM_MODEL 为空，不知道要调用哪个模型。"
        ))

    # ── Admin ───────────────────────────────────────────
    if not ADMIN_PASSWORD:
        warnings.append(ValidationWarning(
            "WARN", "ADMIN_PASSWORD",
            "后台 ADMIN_PASSWORD 为空，/admin 将一律拒绝登录（安全机制，可接受）。"
        ))

    # ── Numeric sanity ──────────────────────────────────
    if ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
        warnings.append(ValidationWarning(
            "FATAL", "ACCESS_TOKEN_EXPIRE_MINUTES",
            f"ACCESS_TOKEN_EXPIRE_MINUTES={ACCESS_TOKEN_EXPIRE_MINUTES}，必须 > 0。"
        ))
    if ANONYMOUS_RATE_LIMIT_MAX < 0:
        warnings.append(ValidationWarning(
            "FATAL", "ANONYMOUS_RATE_LIMIT_MAX",
            f"ANONYMOUS_RATE_LIMIT_MAX={ANONYMOUS_RATE_LIMIT_MAX}，必须 >= 0。"
        ))

    # Strict mode: FATAL → abort startup
    if strict:
        fatals = [w for w in warnings if w.level == "FATAL"]
        if fatals:
            lines = ["\n⚠️  配置校验失败，服务拒绝启动："]
            for w in fatals:
                lines.append(f"  [{w.level}] {w.field}: {w.message}")
            warn_lines = [w for w in warnings if w.level == "WARN"]
            if warn_lines:
                lines.append("\n同时提醒：")
                for w in warn_lines:
                    lines.append(f"  [{w.level}] {w.field}: {w.message}")
            lines.append("\n请在 .env 中修正后再启动服务。")
            raise ConfigError("\n".join(lines))

    return warnings
