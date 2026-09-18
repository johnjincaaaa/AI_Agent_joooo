"""
Jingent AI configuration with startup validation.

Values are loaded from .env file. `validate_config()` MUST be called
at startup to catch missing/invalid values early with a clear error,
instead of failing later with a cryptic 500 on some API call.
"""
import os
import sys
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv

from paths import ensure_env_file

# 运行时 .env 放 %APPDATA%/Jingent/.env（打包后仍可写），首次运行自动从 .env.example 生成
load_dotenv(ensure_env_file())


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
SYSTEM_PROMPT = "你是一个乐于助人的助手，全程中文回答"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")

MODEL = os.getenv("LLM_MODEL") or os.getenv("MODEL", "deepseek-chat")
LLM_MODEL = MODEL
LLM_BASE_URL = (
    os.getenv("LLM_BASE_URL")
    or os.getenv("DASHSCOPE_URL", "https://api.deepseek.com/v1")
)
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")

# Compatibility aliases
DASHSCOPE_URL = LLM_BASE_URL
DASHSCOPE_API_KEY = LLM_API_KEY

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
# Scene presets (chat / office / study / life)
# ==================================================================
SCENE_PRESETS = {
    "chat": {
        "id": "chat",
        "name_zh": "日常闲聊",
        "name_en": "Casual Chat",
        "icon": "💬",
        "system_prompt_zh": "你是Jingent AI，一个友善、健谈的聊天伙伴。请用轻松、自然、口语化的中文与用户交流，像朋友聊天一样。回答简洁有趣，适当使用表情符号，避免过于正式或技术化的语言。话题可以涉及生活、娱乐、情感、兴趣爱好等日常内容。",
        "system_prompt_en": "You are Jingent AI, a friendly and talkative chat companion. Chat naturally, keep answers concise and fun, use emojis appropriately.",
    },
    "office": {
        "id": "office",
        "name_zh": "办公文案",
        "name_en": "Office Writing",
        "icon": "💼",
        "system_prompt_zh": "你是Jingent AI，一位专业的办公文案助手。请用专业、规范、条理清晰的中文回答，内容具体可直接使用。",
        "system_prompt_en": "You are Jingent AI, a professional office writing assistant. Answer in professional, well-structured Chinese.",
        "quick_templates": [
            {"id": "weekly", "name_zh": "周报", "name_en": "Weekly Report", "icon": "📋",
             "prompt_zh": "请帮我写一份工作周报。\n\n请按以下结构输出：\n1. 本周工作内容（按重要性列出 3-5 项）\n2. 工作成果与数据\n3. 遇到的问题与解决方案\n4. 下周工作计划\n5. 需要的支持与资源"},
            {"id": "monthly", "name_zh": "月报", "name_en": "Monthly Report", "icon": "📊",
             "prompt_zh": "请帮我写一份月度工作总结报告。\n\n请按以下结构输出：\n1. 本月工作概述\n2. 重点工作完成情况（附数据指标）\n3. 主要成绩与亮点\n4. 存在的问题与不足\n5. 下月工作计划与目标\n6. 团队协作与跨部门事项"},
            {"id": "email", "name_zh": "工作邮件", "name_en": "Work Email", "icon": "✉️",
             "prompt_zh": "请帮我写一封工作邮件。\n\n请按标准邮件格式输出：\n- 主题：简洁明了，体现核心内容\n- 称呼：恰当得体\n- 正文：开头问候+说明来意，主体分点阐述，结尾明确下一步行动\n- 落款：姓名+日期"},
            {"id": "speech", "name_zh": "演讲稿", "name_en": "Speech", "icon": "🎤",
             "prompt_zh": "请帮我写一篇演讲稿。\n\n请按以下结构输出：\n1. 开场白（问候+自我介绍+引入主题）\n2. 主体部分（3-5 个核心要点，每个配论据/故事/数据）\n3. 情感升华（联系听众，引发共鸣）\n4. 结尾（总结+呼吁行动/金句收尾）"},
            {"id": "meeting", "name_zh": "会议纪要", "name_en": "Meeting Minutes", "icon": "📝",
             "prompt_zh": "请帮我写一份会议纪要。\n\n请按以下结构输出：\n- 会议主题 / 时间 / 地点 / 参会人员\n- 会议议题与讨论要点\n- 会议决议（明确结论）\n- 行动项列表（任务/负责人/截止日期）\n- 下次会议安排"},
        ],
    },
    "study": {
        "id": "study",
        "name_zh": "学习答疑",
        "name_en": "Study Q&A",
        "icon": "📚",
        "system_prompt_zh": "你是Jingent AI，一位耐心的学习辅导老师。请用通俗易懂、循序渐进的中文回答，把复杂概念讲清楚。",
        "system_prompt_en": "You are Jingent AI, a patient study tutor. Explain concepts clearly in step-by-step Chinese.",
        "quick_templates": [
            {"id": "explain", "name_zh": "知识点讲解", "name_en": "Explain Concept", "icon": "💡",
             "prompt_zh": "请帮我讲解一个知识点。\n\n1. 概念定义\n2. 核心原理\n3. 举例说明\n4. 常见误区\n5. 延伸拓展"},
            {"id": "homework", "name_zh": "作业辅导", "name_en": "Homework Help", "icon": "📝",
             "prompt_zh": "请帮我解答一道题目。\n\n1. 题目分析\n2. 解题思路\n3. 详细解答\n4. 方法总结\n5. 举一反三"},
            {"id": "exam", "name_zh": "复习提纲", "name_en": "Review Outline", "icon": "🎯",
             "prompt_zh": "请帮我做一个复习提纲。\n\n1. 知识框架\n2. 核心考点\n3. 重点公式/定理\n4. 典型例题\n5. 易错点汇总"},
        ],
    },
    "life": {
        "id": "life",
        "name_zh": "生活解惑",
        "name_en": "Life Advice",
        "icon": "🌟",
        "system_prompt_zh": "你是Jingent AI，一位贴心的生活顾问。请用温暖、共情、实用的中文回答，语气亲切如朋友。",
        "system_prompt_en": "You are Jingent AI, a caring life advisor. Answer in warm, empathetic, practical Chinese.",
        "quick_templates": [
            {"id": "travel", "name_zh": "旅游攻略", "name_en": "Travel Guide", "icon": "✈️",
             "prompt_zh": "请帮我做一份旅游攻略。\n\n1. 目的地简介\n2. 最佳出行时间\n3. 行程规划（按天）\n4. 必打卡景点\n5. 美食推荐\n6. 住宿建议\n7. 实用Tips"},
            {"id": "emotion", "name_zh": "情感疏导", "name_en": "Emotional Support", "icon": "💗",
             "prompt_zh": "请帮我做一次情感疏导。\n\n1. 共情倾听\n2. 情绪命名\n3. 正向视角\n4. 实际建议\n5. 温暖收尾"},
            {"id": "health", "name_zh": "健康养生", "name_en": "Health Tips", "icon": "💪",
             "prompt_zh": "请给我一些健康养生建议。\n\n1. 问题分析\n2. 饮食建议\n3. 作息建议\n4. 运动建议\n5. 日常调理"},
        ],
    },
}

# ==================================================================
# Tool list & Database
# ==================================================================
TOOL_LIST: list = []

from paths import data_dir

SQLALCHEMY_DATABASE_URL = os.getenv(
    "SQLALCHEMY_DATABASE_URL",
    f"sqlite:///{data_dir() / 'app.db'}",
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


# ==================================================================
# File upload (chat attachments)
# ==================================================================
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp"}
ALLOWED_DOCUMENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
}
ALLOWED_FILE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
    ".pdf", ".doc", ".docx", ".txt",
}
MAX_IMAGE_SIZE = 10 * 1024 * 1024   # 10MB
MAX_DOCUMENT_SIZE = 20 * 1024 * 1024  # 20MB
UPLOAD_DIR = data_dir() / "uploads"
