"""
Jingent AI — FastAPI entrypoint.

Phase-1 重构后：此文件负责「装配」，业务路由逐步拆分到 api/ 子模块。
- 启动顺序：日志 → 配置校验 → 创建 app → 注册路由
"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import os
import sys

# ── 1. 日志：最先初始化，后续所有 logger 都能用上 ──
from app.core.logging_setup import setup_logging
_log_dir = setup_logging()

# ── 2. 配置加载 + 校验 ──
import app.config as config
from app.config import ConfigError, validate_config

# 开发模式（RUNTIME_ENV != prod）：SECRET_KEY 未配也能跑（只打 WARN）
_runtime_env = os.getenv("RUNTIME_ENV", "dev").lower()
try:
    validate_config(strict=(_runtime_env == "prod"))
except ConfigError as e:
    logging.getLogger(__name__).critical(str(e))
    sys.exit(1)

logger = logging.getLogger(__name__)
if _runtime_env != "prod":
    for w in validate_config(strict=False):
        logger.warning("[config][%s] %s: %s", w.level, w.field, w.message)

from app.config import *
from app.core.token_utils import (
    create_access_token, verify_token, get_optional_user_id,
    create_admin_token, verify_admin_token,
)
from app.core.password_utils import hash_password, verify_password, needs_rehash
from app.core.rate_limit import check_anonymous_rate_limit, get_anonymous_remaining
from app.services import promo
from app.core.db import *
import app.tools as tools
from app.tools.skills_registry import get_skill_catalog, resolve_tools
from app.services.job_mock_data import RESUME_TEMPLATES, MOCK_JOBS, match_jobs

# 路由模块
from app.api import chat_routes, job_routes, admin_routes, auth_routes, memory_routes, character_routes, create_routes, pet_market_routes, tts_routes

# Middleware
from app.core.middleware import add_request_middleware

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
from app.core.paths import resource_path, uploads_dir
app.mount("/static", StaticFiles(directory=str(resource_path("static"))), name="static")
UPLOAD_DIR = uploads_dir()
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# 角色系统头像静态资源（/plugins/avatars/xxx.png|webp，与 characters 同级）
_characters_avatars = resource_path("static") / "plugins" / "avatars"
_characters_avatars.mkdir(parents=True, exist_ok=True)
app.mount("/plugins/avatars", StaticFiles(directory=str(_characters_avatars)), name="character-avatars")

# 宠物自定义资源（/plugins/dsh-pet/user-assets/<user_id>/webm|memes|sound/xxx）
from app.core.pet_assets import PET_ASSETS_ROOT
PET_ASSETS_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/plugins/dsh-pet/user-assets", StaticFiles(directory=str(PET_ASSETS_ROOT)), name="pet-user-assets")

# 宠物插件市场资源（/plugins/pets/<pet_id>/webm|preview.png，与 dsh-pet 同级）
from app.core.pet_market import PETS_ROOT
PETS_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/plugins/pets", StaticFiles(directory=str(PETS_ROOT)), name="pet-market-pets")
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory=str(resource_path("templates")))

# 静态资源版本号
import time as _time
ASSET_VERSION = str(int(_time.time()))
templates.env.globals["ASSET_VERSION"] = ASSET_VERSION

# 网页插件系统：静态资源挂载 + 路由注册 + 模板注入
from app.plugins import get_registry
plugin_registry = get_registry()
plugin_registry.install(app, templates)

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
# 确保表结构存在（幂等：create_all 只建缺失表，memories 等新表在此创建）
from app.core.db.seed import init_db
init_db()
logger.info("[Boot] DB schema ensured (init_db)")

# chat_routes 先 bind + include（页面路由 + 技能/场景 API）
chat_routes.bind(templates)
app.include_router(chat_routes.router)
logger.info("[Boot] Chat routes loaded (api/chat_routes.py)")

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

# 记忆（个人陪伴助手：全局 + 细节）+ LLM 配置测试
app.include_router(memory_routes.router)
logger.info("[Boot] Memory routes loaded (api/memory_routes.py)")

# 角色系统（角色市场 / 导入 / 收藏 / 置顶 / 分享 / 绑定 / 人设参数开关）
app.include_router(character_routes.router)
logger.info("[Boot] Character routes loaded (api/character_routes.py)")

# Jingent 创作中心（/chat/create：自定义角色创建 / 草稿 / 审核 / 使用）
app.include_router(create_routes.router)
logger.info("[Boot] Create-center routes loaded (api/create_routes.py)")

# DSH 宠物插件市场（git 导入 / AI 安装 / 切换 / 卸载）
app.include_router(pet_market_routes.router)
logger.info("[Boot] Pet-market routes loaded (api/pet_market_routes.py)")

# 记忆体语音（VoiceStudio 本地语音服务代理：合成 / 音色 / 转录 / 健康检查）
app.include_router(tts_routes.router)
logger.info("[Boot] TTS routes loaded (api/tts_routes.py)")

# 主动发消息（主对话 AI 定时主动开启话题）
from app.core.active_chat import start_active_chat_worker
start_active_chat_worker()
logger.info("[Boot] Active chat worker started")


if __name__ == "__main__":
    # 直接传 app 对象（而非字符串 "main:app"），确保入口稳定
    uvicorn.run(app, host="127.0.0.1", port=8000, workers=1)
