"""
配置包：聚合导出，保持 `from app.config import X` 兼容。

来源：
  - settings.py   —— 运行时环境配置 + 校验
  - scenes.py     —— 场景预设业务数据
  - constants.py  —— 上传白名单等应用常量
"""
from app.config.settings import *          # noqa: F401,F403
from app.config.settings import ConfigError, validate_config
from app.config.scenes import SYSTEM_PROMPT, SCENE_PRESETS
from app.config.constants import (          # noqa: F401
    ALLOWED_IMAGE_TYPES,
    ALLOWED_DOCUMENT_TYPES,
    ALLOWED_FILE_EXTENSIONS,
    MAX_IMAGE_SIZE,
    MAX_DOCUMENT_SIZE,
    UPLOAD_DIR,
    TOOL_LIST,
)

__all__ = [
    # settings
    "ConfigError", "validate_config",
    "SECRET_KEY", "ALGORITHM", "ACCESS_TOKEN_EXPIRE_MINUTES",
    "OLLAMA_URL", "MODEL", "LLM_MODEL", "LLM_BASE_URL", "LLM_API_KEY",
    "DASHSCOPE_URL", "DASHSCOPE_API_KEY",
    "ANONYMOUS_RATE_LIMIT_MAX",
    "ADMIN_USERNAME", "ADMIN_PASSWORD",
    "SQLALCHEMY_DATABASE_URL",
    # scenes
    "SYSTEM_PROMPT", "SCENE_PRESETS",
    # constants
    "ALLOWED_IMAGE_TYPES", "ALLOWED_DOCUMENT_TYPES", "ALLOWED_FILE_EXTENSIONS",
    "MAX_IMAGE_SIZE", "MAX_DOCUMENT_SIZE", "UPLOAD_DIR", "TOOL_LIST",
]
