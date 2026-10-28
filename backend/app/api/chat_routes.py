"""
聊天相关路由和模型 — extracted from main.py.

路径保持不变：无 prefix，直接 /, /chat, /ai/*
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, HTTPException, Request, UploadFile, File, Query,
)
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

import app.config as config
from app.config import (
    ALLOWED_IMAGE_TYPES, ALLOWED_DOCUMENT_TYPES, ALLOWED_FILE_EXTENSIONS,
    MAX_IMAGE_SIZE, MAX_DOCUMENT_SIZE, UPLOAD_DIR, SYSTEM_PROMPT,
    MODEL, DASHSCOPE_URL, DASHSCOPE_API_KEY,
    EMBEDDING_BASE_URL, EMBEDDING_MODEL, EMBEDDING_API_KEY,
)
from app.core.db import get_db, ChatSession, Memory, Message
from app.core.token_utils import verify_token, get_optional_user_id
from app.core.rate_limit import check_anonymous_rate_limit, get_anonymous_remaining
import app.tools as tools
from app.tools.skills_registry import get_skill_catalog, resolve_tools
from app.services import promo

try:
    from langchain.chat_models import init_chat_model
    from langchain.agents import create_agent
    from langchain.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
except ModuleNotFoundError as e:
    logging.getLogger(__name__).warning("Langchain import failed (optional feature): %s", e)


logger = logging.getLogger(__name__)
router = APIRouter()

_templates_ref: Optional[Jinja2Templates] = None


def bind(templates):
    global _templates_ref
    _templates_ref = templates


def _broadcast_pet(event: dict) -> None:
    """向桌宠插件广播 AI 状态事件（惰性导入避免循环依赖）。

    event 形如 {"t": "turn-start"}，与前端 pet.js 的 handleEvent 约定一致。
    """
    try:
        from app.plugins import get_registry
        get_registry().broadcast("dsh-pet", event)
    except Exception as e:
        logger.debug("[pet] 广播失败: %s", e)


def _now_iso() -> str:
    """当前 UTC 时间的 ISO 8601 字符串，前端 new Date(value) 可直接解析。"""
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(value) -> Optional[datetime]:
    """把 ISO 8601 字符串（可能带 Z 后缀/时区）转成 naive 本地 datetime，供 DateTime 列存储。

    无法解析时返回 None（由 DB 列的 default 兜底，避免覆盖为 NULL）。
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        s = str(value).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)  # 转成本地时间并去掉时区，保证 DB 存储一致
        return dt
    except Exception:
        return None


# ==================================================================
# Pydantic 模型
# ==================================================================

class ChatMessage(BaseModel):
    role: str
    message: str
    reactions: dict = {}   # 消息反应 {emoji: count}，主人给 AI 消息点的表情
    created_at: Optional[str] = None   # 消息创建时间（ISO 8601），前端 new Date 直接解析展示
    reply_to: Optional[dict] = None    # 引用消息 {created_at, message}，前端据此渲染引用块并跳转


class ChatRequest(BaseModel):
    history: List[ChatMessage]
    newMessage: str
    open_online: bool = False
    enabled_skills: List[str] = []
    image_paths: List[str] = []
    document_paths: List[str] = []
    lang: str = "zh"
    scene: Optional[str] = None
    llm: Optional[dict] = None   # 用户前端自定义 LLM 配置 {base_url, model, api_key}，缺省回退 .env
    embedding: Optional[dict] = None   # 用户前端自定义向量模型配置 {base_url, model, api_key}，缺省回退 .env
    chat_type: str = "main"      # main=主对话 / secondary=新建会话
    reply_to: Optional[dict] = None    # 引用消息（前端「引用」后携带）
    character_id: Optional[str] = None  # 角色包 ID（主对话人格，缺省用用户当前绑定角色）


class ChatDbRequest(BaseModel):
    chat_data: List[ChatMessage]
    create_time: int
    session_name: str
    chat_type: str = "secondary"   # main=主对话 / secondary=新建会话


class ChatRenameRequest(BaseModel):
    session_time: int
    session_name: str


# ==================================================================
# 辅助函数
# ==================================================================

def augment_message_with_attachments(
        message: str,
        image_paths: List[str],
        document_paths: List[str],
) -> str:
    hints = []
    if image_paths:
        paths_text = "\n".join(f"- {path}" for path in image_paths)
        hints.append(
            f"[系统提示] 用户附带了图片，请使用 image_analyze 工具分析，图片本地路径：\n{paths_text}"
        )
    if document_paths:
        paths_text = "\n".join(f"- {path}" for path in document_paths)
        hints.append(
            f"[系统提示] 用户附带了文档，请使用 document_analyze 工具读取，文档本地路径：\n{paths_text}"
        )
    if not hints:
        return message

    if image_paths and not message.strip():
        base = "请分析这张图片"
    elif document_paths and not message.strip():
        base = "请分析这些文档"
    else:
        base = message.strip() if message.strip() else "请处理附件内容"

    return f"{base}\n\n" + "\n\n".join(hints)


def resolve_enabled_skills(
        enabled_skills: List[str],
        image_paths: List[str],
        document_paths: List[str],
) -> List[str]:
    skills = list(enabled_skills)
    if image_paths and "image_parsing" not in skills:
        skills.append("image_parsing")
    if document_paths and "document_parsing" not in skills:
        skills.append("document_parsing")
    return skills


def build_agent_messages(
        ai_context: List[ChatMessage],
        image_paths: List[str],
        document_paths: List[str],
):
    messages = []
    for i, msg in enumerate(ai_context):
        content = msg.message
        if msg.role == "user" and i == len(ai_context) - 1:
            content = augment_message_with_attachments(content, image_paths, document_paths)
        if msg.role == "user":
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))
    return messages


def _detect_file_kind(content_type: str, suffix: str) -> str:
    if content_type in ALLOWED_IMAGE_TYPES or suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
        return "image"
    return "document"


def _save_upload_file(content: bytes, filename: str, suffix: str) -> Path:
    safe_suffix = suffix if suffix in ALLOWED_FILE_EXTENSIONS else ".bin"
    save_name = f"{uuid.uuid4().hex}{safe_suffix}"
    save_path = UPLOAD_DIR / save_name
    save_path.write_bytes(content)
    return save_path


def build_system_prompt(
        lang: str = "zh",
        scene: Optional[str] = None,
        chat_type: str = "main",
        character_id: Optional[str] = None,
        character_settings: Optional[dict] = None,
        user_id: Optional[int] = None,
) -> str:
    is_en = (lang or "zh").lower().startswith("en")

    # 明确指定了 scene（如 office/study/life）时优先用场景预设
    if scene and scene in config.SCENE_PRESETS:
        preset = config.SCENE_PRESETS[scene]
        return preset["system_prompt_en"] if is_en else preset["system_prompt_zh"]

    if is_en:
        return "You are a helpful assistant. Always respond in English."

    # 按对话类型分化风格：主对话=角色人设（默认女仆大肥鱼），新建会话=标准助手
    if chat_type == "secondary":
        return config.SECONDARY_CHAT_PROMPT

    # 主对话：用角色系统人设（支持角色包 + 人设参数开关）
    try:
        from app.core import characters as charsvc
        char = charsvc.resolve_character(character_id, user_id)
        if char:
            settings = character_settings or charsvc.get_user_settings(user_id)
            return charsvc.build_character_prompt(char, settings)
    except Exception as e:
        logger.warning("[characters] 构建角色人设失败，回退默认: %s", e)

    return config.MAIN_CHAT_PROMPT


def normalize_base_url(base_url: str) -> str:
    """规范化 OpenAI 兼容 base_url。

    中转站常把地址写成裸域名（如 https://api.vst110.cn），
    而 OpenAI 兼容协议要求路径含 /v1（实际请求会拼 /v1/chat/completions）。
    这里自动补齐缺失的 /v1，避免用户填错导致打到中转站网页而非 API。

    规则：
      - 去尾部斜杠
      - 已含 /v1（或 /v1/xxx）则保持
      - 否则补 /v1
    """
    url = (base_url or "").strip().rstrip("/")
    if not url:
        return url
    if "/v1" in url or url.endswith("/v1"):
        return url
    return url + "/v1"


def resolve_llm_config(user_llm: Optional[dict]):
    """用户前端自定义 LLM 配置（base_url/model/api_key），缺省回退 .env。"""
    cfg = user_llm or {}
    return (
        (cfg.get("model") or "").strip() or MODEL,
        normalize_base_url((cfg.get("base_url") or "").strip() or DASHSCOPE_URL),
        (cfg.get("api_key") or "").strip() or DASHSCOPE_API_KEY,
    )


def resolve_embedding_config(user_embedding: Optional[dict]):
    """用户前端自定义向量模型配置（base_url/model/api_key），缺省回退 .env。

    返回 dict（rag.py 用），字段与 settings.EMBEDDING_* 对齐。
    """
    cfg = user_embedding or {}
    base_url = (cfg.get("base_url") or "").strip() or EMBEDDING_BASE_URL
    model = (cfg.get("model") or "").strip() or EMBEDDING_MODEL
    api_key = (cfg.get("api_key") or "").strip() or EMBEDDING_API_KEY
    return {"base_url": base_url, "model": model, "api_key": api_key}


def build_memory_prompt(user_id: Optional[int], db: Session, chat_type: str = "main") -> str:
    """拼记忆块。

    - 主对话（main）：全局画像 + 细节记忆（完整记忆上下文）
    - 新建会话（secondary）：只注入全局画像，不注入细节记忆
    - 未登录用户：无记忆
    """
    if not user_id:
        return ""
    globals_ = (
        db.query(Memory)
        .filter(Memory.user_id == user_id, Memory.type == "global")
        .order_by(Memory.id.asc())
        .all()
    )
    # 细节记忆只在主对话注入
    details = []
    if chat_type == "main":
        details = (
            db.query(Memory)
            .filter(Memory.user_id == user_id, Memory.type == "detail")
            .order_by(Memory.id.desc())
            .limit(15)
            .all()
        )
    if not globals_ and not details:
        return ""
    lines = ["【你记得的关于这位用户的记忆】"]
    if globals_:
        lines.append("· 全局画像：")
        lines += [f"  - {m.content}" for m in globals_]
    if details:
        lines.append("· 细节记忆：")
        lines += [f"  - {m.content}" for m in reversed(details)]  # 旧在前，新在后
    lines.append("请在对话中自然体现你记得这些（主动关心、呼应细节），但不要生硬罗列；")
    lines.append("如果新对话与旧记忆冲突，以用户当前表达为准。")
    return "\n".join(lines)


def run_chat_turn(
        history: List[ChatMessage],
        new_message: str,
        user_id: Optional[int],
        db: Session,
        llm_config: Optional[dict] = None,
        embedding_config: Optional[dict] = None,
        scene: Optional[str] = None,
        lang: str = "zh",
        enabled_skills: Optional[List[str]] = None,
        temperature: float = 0.7,
        open_online: bool = False,
        chat_type: str = "main",
        character_id: Optional[str] = None,
        character_settings: Optional[dict] = None,
):
    """可复用的对话核心：构建人设 + 注入记忆 + 调用 LLM，返回 (ai_reply, new_history)。

    主 chat 和桌宠 /say 共用此函数，保证「同一个 AI 大脑」：
    同一人设（会话绑定角色）、同一记忆、同一会话历史。

    chat_type：main=主对话（角色人设+完整记忆），secondary=新建会话（标准助手+仅全局记忆）。
    character_id：角色包 ID；主对话用它构建人设，缺省回退用户当前绑定角色。

    返回：
        (ai_reply: str, new_history: List[ChatMessage], (model_name, base_url, api_key))
    """
    full_history = list(history)
    full_history.append(ChatMessage(role='user', message=new_message, created_at=_now_iso()))
    ai_context = full_history[-50:]

    # 用户发消息 → 重置主动对话的「连续未回应」计数（/say 桌宠对话也走这里）
    try:
        from app.core.active_chat import reset_unanswered_count
        reset_unanswered_count(user_id)
    except Exception:
        pass

    model_name, base_url, api_key = resolve_llm_config(llm_config)
    model = init_chat_model(
        model=model_name,
        model_provider="openai",
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
    )

    resolved_skills = resolve_enabled_skills(
        enabled_skills or [], [], [],
    )
    tool_list = build_tool_list(open_online, resolved_skills)

    base_system_prompt = build_system_prompt(
        lang, scene, chat_type,
        character_id=character_id,
        character_settings=character_settings,
        user_id=user_id,
    )
    skill_prompts = []
    for sid in resolved_skills:
        sp = get_prompt_skill_system_prompt(sid)
        if not sp:
            sp = get_installed_skill_system_prompt(sid)
        if sp:
            skill_prompts.append(sp)
    if skill_prompts:
        final_system_prompt = base_system_prompt + "\n\n---\n\n".join(skill_prompts)
    else:
        final_system_prompt = base_system_prompt

    memory_prompt = build_memory_prompt(user_id, db, chat_type)
    if memory_prompt:
        final_system_prompt = final_system_prompt + "\n\n" + memory_prompt

    # RAG：主对话注入语义检索到的历史对话（新建会话不注入）
    if chat_type == "main" and user_id:
        try:
            from app.core.rag import get_rag_store
            rag_cfg = resolve_embedding_config(embedding_config)
            rag_hits = get_rag_store().search(user_id, new_message, k=5, embedding_cfg=rag_cfg)
            if rag_hits:
                rag_prompt = "【历史相关对话（语义检索）】\n" + "\n".join(f"  - {h}" for h in rag_hits)
                rag_prompt += "\n请自然参考这些历史内容，但不要生硬复述。"
                final_system_prompt = final_system_prompt + "\n\n" + rag_prompt
        except Exception as e:
            logger.warning("[rag] 检索注入失败: %s", e)

    agent = create_agent(
        model=model,
        system_prompt=final_system_prompt,
        tools=tool_list,
    )

    messages = build_agent_messages(ai_context, [], [])

    result = agent.invoke({"messages": messages})
    for msg in result["messages"]:
        if msg.type == "tool":
            logger.info(f"[调用工具] {msg.name} | {msg.content}")
        elif msg.type == "ai" and msg.content:
            logger.info(f"\n最终AI回答: {msg.content}")
    ai_reply = result["messages"][-1].content

    # 真人连发：按 ||| 拆成多条 AI 消息；ai_reply 去分隔符（桌宠气泡展示用）
    ai_text = str(ai_reply)
    ai_parts = [p.strip() for p in ai_text.split("|||") if p.strip()]
    if not ai_parts:
        ai_parts = [""]
    new_history = full_history + [
        ChatMessage(role="ai", message=p, created_at=_now_iso()) for p in ai_parts
    ]
    return "".join(ai_parts), new_history, (model_name, base_url, api_key)


def _background_extract_memories(
        user_id: int, user_msg: str, ai_reply: str,
        base_url: str, model: str, api_key: str,
) -> None:
    """对话结束后后台抽取记忆（独立 DB 连接，不阻塞响应）。

    纯同步实现，跑在线程里：不依赖事件循环，
    因此在同步路由（/ai/chat）和 async 路由（/ai/chatStream）里都能安全调用。
    """
    try:
        from app.api.memory_routes import extract_facts_sync, save_extracted_facts
        from app.core.db import SessionLocal
        facts = extract_facts_sync(user_msg, ai_reply, base_url, model, api_key)
        if not facts:
            return
        db = SessionLocal()
        try:
            added = save_extracted_facts(db, user_id, facts)
            if added:
                logger.info("[memory] 后台抽取新增 %d 条记忆 (user=%s)", added, user_id)
        finally:
            db.close()
    except Exception as e:
        logger.warning("[memory] 后台抽取异常: %s", e)


def _schedule_memory_extract(
        user_id: int, user_msg: str, ai_reply: str,
        base_url: str, model: str, api_key: str,
) -> None:
    """后台线程启动记忆抽取，任何上下文（同步/异步）都安全。"""
    import threading
    t = threading.Thread(
        target=_background_extract_memories,
        args=(user_id, user_msg, ai_reply, base_url, model, api_key),
        daemon=True,
    )
    t.start()


def _schedule_rag_write(session_id: int, user_id: int) -> None:
    """后台线程把主对话消息写入向量库（独立 session，避免线程复用问题）。"""
    import threading
    def _write():
        try:
            from app.core.db import SessionLocal
            from app.core.rag import get_rag_store
            rag = get_rag_store()
            sdb = SessionLocal()
            try:
                rows = sdb.query(Message).filter(Message.session_id == session_id).all()
                for r in rows:
                    rag.add_message(user_id, r.id, r.content)
            finally:
                sdb.close()
        except Exception as e:
            logger.warning("[rag] 后台写向量失败: %s", e)
    threading.Thread(target=_write, daemon=True).start()


def build_tool_list(open_online: bool, enabled_skills: Optional[List[str]] = None):
    tool_list = list(config.TOOL_LIST)
    tool_list.extend(resolve_tools(enabled_skills or []))
    if open_online:
        tool_list.extend([tools.online, tools.online_intensive])
    return tool_list


def ensure_chat_access(http_request: Request, user_id: Optional[int]) -> Optional[int]:
    if user_id is None:
        return check_anonymous_rate_limit(http_request)
    return None


# ==================================================================
# 页面路由
# ==================================================================

@router.get("/", summary="首页", include_in_schema=False)
def home_page(request: Request):
    return _templates_ref.TemplateResponse(name="home.html", request=request)


@router.get("/chat", summary="聊天页", description="启动入口，返回html")
def chat_page(request: Request, db: Session = Depends(get_db)):
    try:
        promo.record_page_visit(
            db,
            ip=promo.client_ip(request),
            user_agent=request.headers.get("user-agent", ""),
            ref_code=request.query_params.get("ref", ""),
            path="/chat",
        )
    except Exception as e:
        logger.warning(f"[埋点] 访问记录失败：{e}")
    return _templates_ref.TemplateResponse(name="ai.html", request=request)


@router.get("/job", summary="找工作页", description="独立找工作模块：个人画像 · 简历 · 岗位推荐", include_in_schema=False)
def job_page(request: Request):
    return _templates_ref.TemplateResponse(name="job.html", request=request)


# ==================================================================
# 技能 & 场景
# ==================================================================

@router.get("/ai/skills", summary="获取可用技能列表")
def list_skills():
    return {"code": 200, "skills": get_skill_catalog()}


@router.get("/ai/skills/market", summary="获取技能市场列表")
def list_skill_market():
    from app.tools.skills_registry import get_all_skills
    return {"code": 200, **get_all_skills()}


@router.post("/ai/skills/preview", summary="预览技能包（解析zip）")
async def preview_skill_package(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        from app.tools.skill_package_manager import parse_skill_zip
        result = parse_skill_zip(contents)
        return {"code": 200 if result["valid"] else 400, **result}
    except Exception as e:
        return {"code": 500, "error": f"上传失败: {str(e)}"}


@router.post("/ai/skills/install", summary="安装技能包")
async def install_skill_package(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        from app.tools.skill_package_manager import install_skill
        result = install_skill(contents)
        if result["success"]:
            return {"code": 200, "skill": result["skill"]}
        return {"code": 400, "error": result["error"]}
    except Exception as e:
        return {"code": 500, "error": f"安装失败: {str(e)}"}


@router.get("/ai/skills/installed", summary="获取已安装的自定义技能列表")
def list_installed_skills_api():
    from app.tools.skill_package_manager import list_installed_skills
    return {"code": 200, "skills": list_installed_skills()}


@router.delete("/ai/skills/installed/{skill_id}", summary="卸载已安装的自定义技能")
def uninstall_skill_api(skill_id: str):
    from app.tools.skill_package_manager import uninstall_skill
    if uninstall_skill(skill_id):
        return {"code": 200, "message": "卸载成功"}
    return {"code": 404, "error": "技能不存在"}


@router.get("/ai/scenes", summary="获取大众场景模板列表（含快捷模板）")
def list_scenes():
    scenes = []
    for key, preset in config.SCENE_PRESETS.items():
        scene = {
            "id": preset["id"],
            "name_zh": preset["name_zh"],
            "name_en": preset["name_en"],
            "icon": preset["icon"],
        }
        if "quick_templates" in preset:
            scene["quick_templates"] = [
                {
                    "id": t["id"],
                    "name_zh": t["name_zh"],
                    "name_en": t["name_en"],
                    "icon": t["icon"],
                }
                for t in preset["quick_templates"]
            ]
        scenes.append(scene)
    return {"code": 200, "scenes": scenes}


@router.get("/ai/scenes/{scene_id}/templates", summary="获取指定场景的快捷模板详情")
def get_scene_templates(scene_id: str):
    preset = config.SCENE_PRESETS.get(scene_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Scene not found")
    templates = preset.get("quick_templates", [])
    return {"code": 200, "templates": templates}


# ==================================================================
# 文件上传
# ==================================================================

@router.post("/ai/upload-image", summary="上传聊天图片")
async def upload_image(
        http_request: Request,
        file: UploadFile = File(...),
        user_id: Optional[int] = Depends(get_optional_user_id),
):
    result = await _handle_file_upload(http_request, file, user_id)
    if result["kind"] != "image":
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "请使用文档上传接口上传非图片文件"})
    return result


@router.post("/ai/upload-file", summary="上传聊天附件")
async def upload_file(
        http_request: Request,
        file: UploadFile = File(...),
        user_id: Optional[int] = Depends(get_optional_user_id),
):
    return await _handle_file_upload(http_request, file, user_id)


async def _handle_file_upload(
        http_request: Request,
        file: UploadFile,
        user_id: Optional[int],
):
    ensure_chat_access(http_request, user_id)

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_FILE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={"code": 400, "msg": "仅支持图片、PDF、Word(doc/docx)、TXT 文件"},
        )

    kind = _detect_file_kind(file.content_type or "", suffix)
    max_size = MAX_IMAGE_SIZE if kind == "image" else MAX_DOCUMENT_SIZE

    content = await file.read()
    if len(content) > max_size:
        limit_mb = max_size // (1024 * 1024)
        raise HTTPException(status_code=400, detail={"code": 400, "msg": f"文件大小不能超过 {limit_mb}MB"})

    save_path = _save_upload_file(content, file.filename or "file", suffix)

    return {
        "code": 200,
        "path": str(save_path.resolve()),
        "url": f"/uploads/{save_path.name}",
        "kind": kind,
        "name": file.filename or save_path.name,
    }


# ==================================================================
# Quota
# ==================================================================

@router.get("/ai/quota", summary="查询未登录用户今日免费体验剩余次数")
def get_quota(
        http_request: Request,
        user_id: Optional[int] = Depends(get_optional_user_id),
):
    if user_id is not None:
        return {"code": 200, "logged_in": True, "limit": None, "remaining": None}
    return {
        "code": 200,
        "logged_in": False,
        "limit": config.ANONYMOUS_RATE_LIMIT_MAX,
        "remaining": get_anonymous_remaining(http_request),
    }


# ==================================================================
# 聊天核心接口
# ==================================================================

@router.post("/ai/chatStream")
async def chat_stream(
        chat_request: ChatRequest,
        http_request: Request,
        temperature: float = 0.7,
        user_id: Optional[int] = Depends(get_optional_user_id),
        db: Session = Depends(get_db),
):
    remaining = ensure_chat_access(http_request, user_id)

    # 桌宠联动：用户发消息 → 倾听
    _broadcast_pet({"t": "user", "text": chat_request.newMessage})

    # 用户发消息 → 重置主动对话的「连续未回应」计数（恢复主动发消息）
    try:
        from app.core.active_chat import reset_unanswered_count
        reset_unanswered_count(user_id)
    except Exception:
        pass

    full_history = chat_request.history.copy()
    full_history.append(ChatMessage(
        role='user', message=chat_request.newMessage, created_at=_now_iso(),
        reply_to=chat_request.reply_to,
    ))
    ai_context = full_history[-50:]

    model_name, base_url, api_key = resolve_llm_config(chat_request.llm)
    model = init_chat_model(
        model=model_name,
        model_provider="openai",
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
    )
    enabled_skills = resolve_enabled_skills(
        chat_request.enabled_skills,
        chat_request.image_paths,
        chat_request.document_paths,
    )
    tool_list = build_tool_list(chat_request.open_online, enabled_skills)

    from app.tools.skills_registry import get_prompt_skill_system_prompt
    from app.tools.skill_package_manager import get_installed_skill_system_prompt
    base_system_prompt = build_system_prompt(
        chat_request.lang, chat_request.scene, chat_request.chat_type,
        character_id=chat_request.character_id,
        character_settings=None,
        user_id=user_id,
    )
    skill_prompts = []
    for sid in enabled_skills:
        sp = get_prompt_skill_system_prompt(sid)
        if not sp:
            sp = get_installed_skill_system_prompt(sid)
        if sp:
            skill_prompts.append(sp)
    if skill_prompts:
        final_system_prompt = base_system_prompt + "\n\n---\n\n".join(skill_prompts)
    else:
        final_system_prompt = base_system_prompt

    memory_prompt = build_memory_prompt(user_id, db, chat_request.chat_type)
    if memory_prompt:
        final_system_prompt = final_system_prompt + "\n\n" + memory_prompt

    # RAG：主对话注入语义检索到的历史对话（新建会话不注入）
    if chat_request.chat_type == "main" and user_id:
        try:
            from app.core.rag import get_rag_store
            rag_cfg = resolve_embedding_config(chat_request.embedding)
            rag_hits = get_rag_store().search(user_id, chat_request.newMessage, k=5, embedding_cfg=rag_cfg)
            if rag_hits:
                rag_prompt = "【历史相关对话（语义检索）】\n" + "\n".join(f"  - {h}" for h in rag_hits)
                rag_prompt += "\n请自然参考这些历史内容，但不要生硬复述。"
                final_system_prompt = final_system_prompt + "\n\n" + rag_prompt
        except Exception as e:
            logger.warning("[rag] 检索注入失败: %s", e)

    agent = create_agent(
        model=model,
        system_prompt=final_system_prompt,
        tools=tool_list,
    )

    messages = build_agent_messages(
        ai_context,
        chat_request.image_paths,
        chat_request.document_paths,
    )

    async def generate():
        buffer = ""          # 流式缓冲：跨 chunk 累积，检测 ||| 分隔符
        parts: List[str] = []  # 拆分后的多条回复

        # 桌宠联动：开始思考
        _broadcast_pet({"t": "turn-start"})

        async for msg_chunk, metadata in agent.astream(
                {"messages": messages},
                stream_mode="messages",
        ):
            if msg_chunk.content:
                buffer += msg_chunk.content
                # 检测「|||」分隔符：真人连发多条消息
                while "|||" in buffer:
                    idx = buffer.index("|||")
                    segment = buffer[:idx]
                    buffer = buffer[idx + 3:]
                    parts.append(segment)
                    if segment:
                        # 桌宠联动：逐字输出 → 嘴巴动
                        _broadcast_pet({"t": "delta", "text": segment})
                        yield f"data: {segment}\n\n"
                    # 通知前端：本条结束，开新气泡
                    yield "data: [MSG_SPLIT]\n\n"

        # flush 剩余缓冲
        if buffer:
            parts.append(buffer)
            _broadcast_pet({"t": "delta", "text": buffer})
            yield f"data: {buffer}\n\n"

        # 清理空段；全部为空时保留一条空回复，避免历史丢失
        parts = [p.strip() for p in parts if p.strip()]
        if not parts:
            parts = [""]
        full_ai_reply = "".join(parts)

        ai_messages = [ChatMessage(role="ai", message=p, created_at=_now_iso()) for p in parts]
        final_history = full_history + ai_messages

        yield f"data: [HISTORY] {json.dumps([m.model_dump() for m in final_history], ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

        # 桌宠联动：结束 → 完成
        _broadcast_pet({"t": "turn-end", "status": "success"})

        # 对话结束后台抽取记忆（不阻塞 SSE）
        if user_id and full_ai_reply:
            _schedule_memory_extract(
                user_id, chat_request.newMessage, full_ai_reply,
                base_url, model_name, api_key,
            )

    headers = {}
    if remaining is not None:
        headers["X-Anon-Remaining"] = str(remaining)
        headers["Access-Control-Expose-Headers"] = "X-Anon-Remaining"
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers=headers,
    )


@router.post("/ai/chat", summary='AI 聊天',
             description="""构建完整对话历史,取最后20条传给 AI，返回完整新历史给前端，前端同步内存""")
def ai_chat(
        chat_request: ChatRequest,
        http_request: Request,
        temperature: float = 0.7,
        user_id: Optional[int] = Depends(get_optional_user_id),
        db: Session = Depends(get_db),
):
    ensure_chat_access(http_request, user_id)

    # 桌宠联动：用户发消息
    _broadcast_pet({"t": "user", "text": chat_request.newMessage})

    # 用户发消息 → 重置主动对话的「连续未回应」计数（恢复主动发消息）
    try:
        from app.core.active_chat import reset_unanswered_count
        reset_unanswered_count(user_id)
    except Exception:
        pass

    full_history = chat_request.history.copy()
    full_history.append(ChatMessage(
        role='user', message=chat_request.newMessage, created_at=_now_iso(),
        reply_to=chat_request.reply_to,
    ))
    ai_context = full_history[-50:]

    model_name, base_url, api_key = resolve_llm_config(chat_request.llm)
    model = init_chat_model(
        model=model_name,
        model_provider="openai",
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
    )
    resolved_skills = resolve_enabled_skills(
        chat_request.enabled_skills,
        chat_request.image_paths,
        chat_request.document_paths,
    )
    tool_list = build_tool_list(
        chat_request.open_online,
        resolved_skills,
    )

    from app.tools.skills_registry import get_prompt_skill_system_prompt
    from app.tools.skill_package_manager import get_installed_skill_system_prompt
    base_system_prompt = build_system_prompt(
        chat_request.lang, chat_request.scene, chat_request.chat_type,
        character_id=chat_request.character_id,
        character_settings=None,
        user_id=user_id,
    )
    skill_prompts = []
    for sid in resolved_skills:
        sp = get_prompt_skill_system_prompt(sid)
        if not sp:
            sp = get_installed_skill_system_prompt(sid)
        if sp:
            skill_prompts.append(sp)
    if skill_prompts:
        final_system_prompt = base_system_prompt + "\n\n---\n\n".join(skill_prompts)
    else:
        final_system_prompt = base_system_prompt

    memory_prompt = build_memory_prompt(user_id, db, chat_request.chat_type)
    if memory_prompt:
        final_system_prompt = final_system_prompt + "\n\n" + memory_prompt

    # RAG：主对话注入语义检索到的历史对话（新建会话不注入）
    if chat_request.chat_type == "main" and user_id:
        try:
            from app.core.rag import get_rag_store
            rag_cfg = resolve_embedding_config(chat_request.embedding)
            rag_hits = get_rag_store().search(user_id, chat_request.newMessage, k=5, embedding_cfg=rag_cfg)
            if rag_hits:
                rag_prompt = "【历史相关对话（语义检索）】\n" + "\n".join(f"  - {h}" for h in rag_hits)
                rag_prompt += "\n请自然参考这些历史内容，但不要生硬复述。"
                final_system_prompt = final_system_prompt + "\n\n" + rag_prompt
        except Exception as e:
            logger.warning("[rag] 检索注入失败: %s", e)

    agent = create_agent(
        model=model,
        system_prompt=final_system_prompt,
        tools=tool_list,
    )

    messages = build_agent_messages(
        ai_context,
        chat_request.image_paths,
        chat_request.document_paths,
    )
    # 桌宠联动：开始思考
    _broadcast_pet({"t": "turn-start"})

    try:
        result = agent.invoke({"messages": messages})
        for msg in result["messages"]:
            if msg.type == "tool":
                logger.info(f"[调用工具] {msg.name} | {msg.content}")
                # 桌宠联动：工具调用 → 忙碌
                _broadcast_pet({"t": "tool-call", "name": msg.name})
            elif msg.type == "ai" and msg.content:
                logger.info(f"\n最终AI回答: {msg.content}")
        ai_reply = result["messages"][-1].content

        # 真人连发：按 ||| 拆成多条 AI 消息（与 chat_stream 保持一致）
        ai_text = str(ai_reply)
        ai_parts = [p.strip() for p in ai_text.split("|||") if p.strip()]
        if not ai_parts:
            ai_parts = [""]
        final_history = full_history + [
            ChatMessage(role="ai", message=p, created_at=_now_iso()) for p in ai_parts
        ]

        # 桌宠联动：结束 → 完成
        _broadcast_pet({"t": "turn-end", "status": "success"})

        # 对话结束后台抽取记忆（不阻塞响应）
        if user_id and ai_reply:
            _schedule_memory_extract(
                user_id, chat_request.newMessage, str(ai_reply),
                base_url, model_name, api_key,
            )

        return {
            "code": 200,
            "content": ai_reply,
            "new_history": final_history
        }
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail={"code": 500, "msg": f"异常：{str(error)}"}
        )


# ==================================================================
# 聊天数据库 CRUD
# ==================================================================

@router.post('/ai/chat/savaToDb', summary='接收数据并存入数据库',
             description=""" 按 【user_id + 秒级时间】 查询,数据更新或创建。消息原子化存 Message 表，同时保留 session.messages 兼容。""")
def ai_savaToDb(
        request: ChatDbRequest,
        db: Session = Depends(get_db),
        user_id: int = Depends(verify_token)
):
    session_time = request.create_time

    existing_session = db.query(ChatSession).filter(
        ChatSession.user_id == user_id,
        ChatSession.session_time == session_time
    ).first()

    try:
        chat_data = [m.model_dump() for m in request.chat_data]

        chat_type = request.chat_type if request.chat_type in ("main", "secondary") else "secondary"

        if existing_session:
            existing_session.session_name = request.session_name
            # 兼容：保留整段 JSON（旧读取路径）
            existing_session.messages = chat_data
            existing_session.chat_type = chat_type
            session = existing_session
        else:
            session = ChatSession(
                user_id=user_id,
                session_name=request.session_name,
                session_time=session_time,
                messages=chat_data,
                chat_type=chat_type,
            )
            db.add(session)
            db.flush()  # 拿到 session.id

        # 原子化：同步 Message 表（先删旧再写新，保证与 chatData 一致）
        db.query(Message).filter(Message.session_id == session.id).delete()
        for m in chat_data:
            role = m.get("role", "user")
            content = m.get("message") or m.get("content") or ""
            if not content:
                continue
            msg_kwargs = dict(
                session_id=session.id,
                user_id=user_id,
                role="ai" if role == "ai" else "user",
                content=str(content),
                reactions=m.get("reactions") or {},
            )
            # 保留每条消息原始时间戳；缺失时才用 DB 列的 default（避免覆盖为 NULL/同一时刻）
            created_at = _parse_dt(m.get("created_at"))
            if created_at is not None:
                msg_kwargs["created_at"] = created_at
            db.add(Message(**msg_kwargs))

        db.commit()

        # RAG：主对话消息写入向量库（后台线程，不阻塞保存；独立 session 避免线程问题）
        if chat_type == "main":
            _schedule_rag_write(session.id, user_id)
        return {"code": 200, "msg": "保存/更新成功", "session_id": session.id}

    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={"code": 500, "msg": f"异常：{str(error)}"}
        )


@router.get('/ai/chat/history', summary='读取数据库chat_sessions中的messages',
            description="""需要加密 ！！ 消息原子化后从 Message 表重组，回退旧 JSON。""")
def ai_history(
        user_id: int = Depends(verify_token),
        session_time: int = Query(None),
        is_Load_All: bool = Query(False),
        db: Session = Depends(get_db)
):
    def _session_messages(session) -> list:
        """从 Message 表重组消息（原子化路径），回退旧 JSON。

        reply_to 只存在于 session.messages JSON（Message 表未存），
        重组时按顺序从 JSON 回填，保证引用块与跳转不丢。
        """
        legacy = session.messages or []
        # 只保留有 message 的项，与 ai_savaToDb 写 Message 表时「跳过空消息」保持一致，避免下标错位
        legacy_reply = [
            m.get("reply_to")
            for m in legacy
            if isinstance(m, dict) and m.get("message")
        ]
        rows = (
            db.query(Message)
            .filter(Message.session_id == session.id)
            .order_by(Message.id.asc())
            .all()
        )
        if rows:
            result = []
            for i, m in enumerate(rows):
                item = {
                    "role": m.role,
                    "message": m.content,
                    "reactions": m.reactions or {},
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                reply = legacy_reply[i] if i < len(legacy_reply) else None
                if reply:
                    item["reply_to"] = reply
                result.append(item)
            return result
        # 回退：旧 JSON（未迁移或历史遗留）
        return [
            {
                "role": m.get("role", "user"),
                "message": m.get("message", ""),
                "reactions": m.get("reactions", {}),
                "created_at": m.get("created_at"),
                "reply_to": m.get("reply_to"),
            }
            for m in legacy if isinstance(m, dict) and m.get("message")
        ]

    # 无会话记录是正常情况，返回 200 + 空结果，不抛 500。
    if is_Load_All:
        existing_sessions = db.query(ChatSession).filter(
            ChatSession.user_id == user_id,
        ).order_by(ChatSession.session_time.desc()).all()

        result = [
            {
                "session_name": item.session_name,
                "session_time": item.session_time,
                "chat_type": item.chat_type or "secondary",
                "messages": _session_messages(item),
            }
            for item in existing_sessions
        ]
        return {
            "code": 200,
            "chat_sessions": result,
        }

    existing_session = db.query(ChatSession).filter(
        ChatSession.user_id == user_id,
        ChatSession.session_time == session_time
    ).first()

    if existing_session:
        return {
            "code": 200,
            "messages": _session_messages(existing_session),
            "session_name": existing_session.session_name,
            "chat_type": existing_session.chat_type or "secondary",
        }
    return {
        "code": 200,
        "messages": None,
        "session_name": None,
    }


@router.post('/ai/chat/rename', summary='重命名会话')
def ai_chat_rename(
        request: ChatRenameRequest,
        db: Session = Depends(get_db),
        user_id: int = Depends(verify_token)
):
    session = db.query(ChatSession).filter(
        ChatSession.user_id == user_id,
        ChatSession.session_time == request.session_time
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "会话不存在"})
    session.session_name = request.session_name.strip()[:100] or session.session_name
    db.commit()
    return {"code": 200, "msg": "已重命名"}


@router.delete('/ai/chat/delete', summary='删除会话')
def ai_chat_delete(
        session_time: int = Query(..., description="会话时间戳"),
        db: Session = Depends(get_db),
        user_id: int = Depends(verify_token)
):
    session = db.query(ChatSession).filter(
        ChatSession.user_id == user_id,
        ChatSession.session_time == session_time
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "会话不存在"})
    db.delete(session)
    db.commit()
    return {"code": 200, "msg": "已删除"}
