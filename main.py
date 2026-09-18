"""
Jingent AI — FastAPI entrypoint.

Phase-1 重构后：此文件负责「装配」，业务路由逐步拆分到 api/ 子模块。
- 启动顺序：日志 → 配置校验 → 创建 app → 注册路由
"""
from sqlalchemy.orm import Session
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import os
import sys
from pathlib import Path

# ── 1. 日志：最先初始化，后续所有 logger 都能用上 ──
from logging_setup import setup_logging
_log_dir = setup_logging()

# ── 2. 配置加载 + 校验 ──
import config
from config import ConfigError, validate_config

# 桌面开发模式：SECRET_KEY 未配也能跑（只打 WARN）
_in_desktop_env = Path("src-tauri/Cargo.toml").exists()
try:
    validate_config(strict=not _in_desktop_env)
except ConfigError as e:
    logging.getLogger(__name__).critical(str(e))
    sys.exit(1)

logger = logging.getLogger(__name__)
if _in_desktop_env:
    for w in validate_config(strict=False):
        logger.warning("[config][%s] %s: %s", w.level, w.field, w.message)

from config import *
from token_utils import (
    create_access_token, verify_token, get_optional_user_id,
    create_admin_token, verify_admin_token,
)
from password_utils import hash_password, verify_password, needs_rehash
from rate_limit import check_anonymous_rate_limit, get_anonymous_remaining
from services import promo
from sqlOrm import *
import tools
from tools.skills_registry import get_skill_catalog, resolve_tools
from services.job_mock_data import RESUME_TEMPLATES, MOCK_JOBS, match_jobs

# 路由模块
from api import jinclaw_routes, chat_routes, job_routes, admin_routes, auth_routes
from api.chat_routes import ensure_chat_access

# Middleware
from middleware import add_request_middleware

try:
    from langchain.chat_models import init_chat_model
    from langchain.agents import create_agent
    from langchain.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
except ModuleNotFoundError as e:
    logger.warning("Langchain import failed (optional feature): %s", e)

# ── 3. FastAPI app 初始化 ──
app = FastAPI(
    title="Jingent AI",
    description="Jingent — AI 聊天 + 代码写作助手",
    version="1.0",
)
from paths import resource_path, data_dir
app.mount("/static", StaticFiles(directory=str(resource_path("static"))), name="static")
UPLOAD_DIR = data_dir() / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory=str(resource_path("templates")))

# 静态资源版本号
import time as _time
ASSET_VERSION = str(int(_time.time()))
templates.env.globals["ASSET_VERSION"] = ASSET_VERSION

# CORS：dev 开 *，prod 读 CORS_ORIGINS 环境变量
env = os.getenv("RUNTIME_ENV", "dev").lower()
cors_origins = ["*"] if env == "dev" else os.getenv("CORS_ORIGINS", "http://localhost:*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info("[Boot] CORS = %s  (RUNTIME_ENV=%s)", cors_origins, env)

# Request ID 中间件
add_request_middleware(app)
logger.info("[Boot] Request-ID middleware enabled")


@app.get("/health", summary="健康检查", include_in_schema=False)
def health_check():
    return {"status": "ok"}


# ==================== 路由装配 ====================
# chat_routes 必须先 bind + include（因为 jinclaw 依赖 ensure_chat_access）
chat_routes.bind(templates)
app.include_router(chat_routes.router)
logger.info("[Boot] Chat routes loaded (api/chat_routes.py)")

# Jinclaw Coding Agent
jinclaw_routes.bind(templates, ensure_chat_access)
app.include_router(jinclaw_routes.router)
logger.info("[Boot] Jinclaw routes loaded (api/jinclaw_routes.py)")

# 找工作
app.include_router(job_routes.router)
logger.info("[Boot] Job routes loaded (api/job_routes.py)")

# 推广 + 后台管理
admin_routes.bind(templates)
app.include_router(admin_routes.router)
logger.info("[Boot] Admin/Promo routes loaded (api/admin_routes.py)")

# 认证 / 用户
app.include_router(auth_routes.router)
logger.info("[Boot] Auth routes loaded (api/auth_routes.py)")


if __name__ == "__main__":
    # 直接传 app 对象（而非字符串 "main:app"），PyInstaller 打包后也能正常启动
    uvicorn.run(app, host="127.0.0.1", port=8000, workers=1)
