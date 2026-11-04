"""
聊天相关路由和模型 — extracted from main.py.

路径保持不变：无 prefix，直接 /, /chat, /ai/*
"""
import hashlib
import json
import logging
import math
import time
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


# ===================== token 用量估算 & 落库 =====================
def estimate_tokens(text: str) -> int:
    """粗略估算 token：中文 1 字 ≈ 1 token，英文/其它按 4 字符 ≈ 1 token。"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
    other = len(text) - cjk
    return cjk + max(0, other // 4)


def _record_chat_tokens(request_id: str, tokens_in: int, tokens_out: int):
    """后台线程把 chat 请求的 token 用量写回 request_logs（按 request_id 关联）。

    middleware 也是异步写库，这里重试最多 6 次（每次 0.5s），
    等 middleware 先把 request_logs 行落库后再更新 token。
    """
    import threading

    def _update():
        from app.core.db import SessionLocal, RequestLog
        import time as _time
        for _ in range(6):
            db = SessionLocal()
            try:
                row = db.query(RequestLog).filter(RequestLog.request_id == request_id).first()
                if row:
                    row.tokens_in = tokens_in
                    row.tokens_out = tokens_out
                    db.commit()
                    db.close()
                    return
                db.close()
            except Exception:
                try:
                    db.close()
                except Exception:
                    pass
            _time.sleep(0.5)

    try:
        threading.Thread(target=_update, daemon=True).start()
    except Exception:
        pass



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
    character_id: Optional[str] = None  # 角色包 ID（主对话按灵魂隔离历史）


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


def build_memory_prompt(user_id: Optional[int], db: Session, chat_type: str = "main",
                        character_id: Optional[str] = None, query: Optional[str] = None) -> str:
    """拼记忆块（按角色隔离）。

    - 主对话（main）：全局画像 + 细节记忆（语义召回 top-K）
    - 新建会话（secondary）：只注入全局画像，不注入细节记忆
    - 未登录用户：无记忆
    - character_id：角色 ID；缺省用当前绑定角色（不同人设记忆独立）
    - query：当前用户输入，用于细节记忆语义召回
    """
    if not user_id:
        return ""
    try:
        from app.core import characters as charsvc
        cid = character_id or charsvc.get_current_character_id(user_id) or "maid"
    except Exception:
        cid = character_id or "maid"
    # 全局画像：用户级、跨角色共享，每次对话固定全量注入（不按角色隔离）
    globals_ = (
        db.query(Memory)
        .filter(Memory.user_id == user_id, Memory.type == "global")
        .order_by(Memory.id.asc())
        .all()
    )
    # 细节记忆只在主对话注入，且语义召回 top-K（docs 模块3：不无脑全塞，控 token）
    details = []
    if chat_type == "main":
        try:
            from app.core import memory_engine as me
            recalled, _qvec = me.recall_details(db, user_id, cid, query or "", k=5)
            details = [r for r in recalled if r.get("similarity", 0) > 0]
            # 若 embedding 服务不可用，recall 已降级按权重取最近 k 条，仍可用
            if not details:
                details = recalled
            # 召回后更新访问热度（不阻塞主流程，weight 持久化）
            ids = [r["id"] for r in details]
            if ids:
                try:
                    me.mark_recalled(db, ids)
                except Exception:
                    pass
        except Exception as e:
            logger.warning("[memory] 语义召回失败，回退最近记忆: %s", e)
            details = (
                db.query(Memory)
                .filter(Memory.user_id == user_id, Memory.character_id == cid,
                        Memory.type == "detail")
                .order_by(Memory.id.desc())
                .limit(5)
                .all()
            )
    if not globals_ and not details:
        return ""
    lines = []
    if globals_:
        lines.append("【全局画像 · 最高优先级硬性约束，必须无条件遵守】")
        lines += [f"  - {m.content}" for m in globals_]
        lines.append("以上全局画像是用户的核心设定与硬性要求，任何情况下都不得违背。")
    if details:
        lines.append("【你记得的关于这位用户的细节记忆 · 仅供参考】")
        for d in details:
            content = d.content if hasattr(d, "content") else d.get("content")
            lines.append(f"  - {content}")
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

    # 解析有效角色 ID（记忆/向量隔离用）
    try:
        from app.core import characters as charsvc
        active_cid = character_id or charsvc.get_current_character_id(user_id) or "maid"
    except Exception:
        active_cid = character_id or "maid"

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

    memory_prompt = build_memory_prompt(user_id, db, chat_type, character_id=active_cid, query=new_message)
    if memory_prompt:
        # 记忆块放最前面：全局画像是最高优先级硬性约束
        final_system_prompt = memory_prompt + "\n\n" + final_system_prompt

    # RAG：主对话注入语义检索到的历史对话（新建会话不注入）
    if chat_type == "main" and user_id:
        try:
            from app.core.rag import get_rag_store
            rag_cfg = resolve_embedding_config(embedding_config)
            rag_hits = get_rag_store().search(user_id, new_message, k=5, embedding_cfg=rag_cfg,
                                              character_id=active_cid)
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
        user_id: int,
        base_url: str, model: str, api_key: str,
        character_id: Optional[str] = None,
) -> None:
    """每累计 20 轮触发：后台抽取最近 20 轮对话历史（独立 DB 连接，不阻塞响应）。

    纯同步实现，跑在线程里：不依赖事件循环，
    因此在同步路由（/ai/chat）和 async 路由（/ai/chatStream）里都能安全调用。
    """
    try:
        from app.api.memory_routes import extract_facts_from_history_sync, save_extracted_facts
        from app.core.db import SessionLocal
        db = SessionLocal()
        try:
            cid = character_id or "maid"
            # 该用户该角色最近 40 条 user/ai 消息（≈20 轮）
            rows = (
                db.query(Message)
                .filter(Message.user_id == user_id,
                        Message.character_id == cid,
                        Message.role.in_(["user", "ai"]))
                .order_by(Message.id.desc())
                .limit(40)
                .all()
            )
            if len(rows) < 20:
                return  # 不足 20 轮，不抽取
            rows = list(reversed(rows))  # 时间正序
            history_text = "\n".join(
                f"{'用户' if r.role == 'user' else 'AI'}：{r.content}" for r in rows
            )
            facts = extract_facts_from_history_sync(history_text, base_url, model, api_key)
            if not facts:
                return
            added = save_extracted_facts(db, user_id, facts, character_id=character_id)
            if added:
                logger.info("[memory] 20轮批量抽取新增 %d 条记忆 (user=%s, character=%s)",
                            added, user_id, character_id)
        finally:
            db.close()
    except Exception as e:
        logger.warning("[memory] 后台抽取异常: %s", e)


def _schedule_memory_extract(
        user_id: int,
        base_url: str, model: str, api_key: str,
        character_id: Optional[str] = None,
) -> None:
    """每累计 20 轮触发一次记忆抽取（异步，不阻塞对话流）。"""
    import threading
    t = threading.Thread(
        target=_background_extract_memories,
        args=(user_id, base_url, model, api_key, character_id),
        daemon=True,
    )
    t.start()


def _schedule_rag_write(session_id: int, user_id: int, character_id: Optional[str] = None) -> None:
    """后台线程把主对话消息写入向量库（独立 session，避免线程复用问题，按角色隔离）。"""
    import threading
    def _write():
        try:
            from app.core.db import SessionLocal
            from app.core.rag import get_rag_store
            rag = get_rag_store()
            sdb = SessionLocal()
            try:
                q = sdb.query(Message).filter(Message.session_id == session_id)
                if character_id:
                    q = q.filter(Message.character_id == character_id)
                rows = q.all()
                for r in rows:
                    rag.add_message(user_id, r.id, r.content,
                                    character_id=character_id or (r.character_id or "maid"))
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


@router.get("/chat/create", summary="Jingent创作中心", include_in_schema=False)
def create_center_page(request: Request):
    return _templates_ref.TemplateResponse(name="create.html", request=request)


@router.get("/chat/create/edit", summary="Jingent创作中心 · 捏小人编辑器", include_in_schema=False)
def create_edit_page(request: Request):
    return _templates_ref.TemplateResponse(name="create_edit.html", request=request)


# ==================================================================
# 记忆银河（/chat/memory）—— 把长期记忆画成旋臂星系
# ==================================================================

_MG_R = 1000
_MG_ARMS = 4
_MG_TAU = {
    'soul': 36500, 'user': 36500, 'person': 400, 'preference': 300, 'fact': 300,
    'plan': 240, 'lesson': 400, 'topic': 300, 'event': 45, 'misc': 60, 'feeling': 150,
    'digest_day': 999, 'digest_week': 999, 'digest_month': 999, 'impression': 300,
    'rules': 240, 'project': 300,
}
_MG_KIND = {
    'soul': 'identity', 'user': 'identity', 'rules': 'plan',
    'person': 'fact', 'preference': 'fact', 'fact': 'fact', 'project': 'fact',
    'plan': 'plan', 'lesson': 'conclusion', 'topic': 'conclusion',
    'digest_day': 'conclusion', 'digest_week': 'conclusion', 'digest_month': 'conclusion',
    'impression': 'conclusion', 'event': 'event', 'misc': 'event', 'feeling': 'feeling', 'diary': 'diary',
}
_MG_SHELL_R = [[0.02, 0.11], [0.14, 0.44], [0.44, 0.72], [0.72, 1.0]]

# 细节记忆分类 → 银河 rawKind（决定半衰期 τ 与颜色）
_MG_CAT_KIND = {
    '计划': 'plan', '目标计划': 'plan', '约定': 'plan',
    '事件': 'event', '重要事件': 'event',
    '情绪状态': 'feeling', '心情': 'feeling',
    '个人喜好': 'preference', '喜好偏好': 'preference', '偏好': 'preference',
    '个人信息': 'fact', '其他': 'fact', '学习': 'topic', '工作': 'fact',
}


def _mg_hash(s: str) -> bytes:
    return hashlib.sha1(s.encode('utf-8')).digest()


def _mg_u01(b: bytes, i: int) -> float:
    return b[i % len(b)] / 255.0


def _mg_gauss(b: bytes, i: int) -> float:
    a = _mg_u01(b, i) or 0.5
    c = _mg_u01(b, i + 7) or 0.5
    return math.sqrt(-2 * math.log(a)) * math.cos(2 * math.pi * c) * 0.5


def _mg_ts(v) -> int:
    """datetime / str / int → 毫秒时间戳；无法解析返回 0。"""
    if v is None:
        return 0
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, datetime):
        return int(v.timestamp() * 1000)
    s = str(v)
    try:
        return int(datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp() * 1000)
    except Exception:
        return 0


def _memory_to_raw_kind(category: str) -> str:
    c = (category or '').strip()
    for key, kind in _MG_CAT_KIND.items():
        if key in c:
            return kind
    return 'fact'


def build_memory_galaxy(stars_raw, messages_raw, now_ms: int) -> dict:
    """把记忆/消息排成银河（复刻 dsh-memory-galaxy 的 lib/data.js layout 算法）。"""
    # 1) 统一星体：算 tau / ageDays / hitDays / effAge / strength
    stars = []
    for s in stars_raw:
        raw_kind = s.get('rawKind', 'fact')
        tau = _MG_TAU.get(raw_kind, 240)
        at = int(s.get('at') or 0) or now_ms
        last_hit = int(s.get('lastHitAt') or 0)
        age_days = max(0, (now_ms - at) / 86400000.0)
        hit_days = max(0, (now_ms - last_hit) / 86400000.0) if last_hit else None
        eff_age = age_days if hit_days is None else min(age_days, hit_days * 0.55)
        weight = max(1.0, min(4.0, float(s.get('weight') or 1)))
        strength = (weight ** 1.5) * math.exp(-eff_age / tau)
        stars.append({
            'id': str(s.get('id')), 'rawKind': raw_kind,
            'kind': _MG_KIND.get(raw_kind, 'fact'),
            'weight': weight, 'at': at, 'lastHitAt': last_hit,
            'pin': bool(s.get('pin')), 'title': str(s.get('title') or ''),
            'text': str(s.get('text') or ''), 'tags': list(s.get('tags') or []),
            'source': s.get('source', 'jingent'),
            'tau': tau, 'ageDays': round(age_days, 2),
            'hitDays': None if hit_days is None else round(hit_days, 2),
            'strength': strength,
        })

    # 2) 分层：pin/identity → 核心(0)；其余按强度排名 55/15/15
    core = [x for x in stars if x['pin'] or x['kind'] == 'identity']
    rest = sorted([x for x in stars if not (x['pin'] or x['kind'] == 'identity')],
                  key=lambda x: -x['strength'])
    for x in core:
        x['shell'] = 0
    n_rest = len(rest)
    for i, x in enumerate(rest):
        f = i / max(1, n_rest - 1)
        x['shell'] = 1 if f < 0.55 else (2 if f < 0.85 else 3)

    # 3) 摆位
    all_stars = core + rest
    for i, s in enumerate(all_stars):
        h = _mg_hash(s['id'] + '|' + str(i))
        r0, r1 = _MG_SHELL_R[s['shell']]
        shell0 = 1 if s['shell'] == 0 else 0
        frac = 0.5 + 0.5 * _mg_u01(h, 3) + (0 if s['shell'] == 0 else 0.25 * (1 - min(1, s['strength'] / 4)))
        rr = min(r1, r0 + (r1 - r0) * min(1, frac * 0.85))
        arm = int(math.floor(_mg_u01(h, 5) * _MG_ARMS)) % _MG_ARMS
        theta = (arm / _MG_ARMS) * math.pi * 2 - 2.6 * math.log(rr * 6 + 1) + (_mg_u01(h, 9) - 0.5) * 1.30
        radius = _MG_R * rr * (1 + (_mg_u01(h, 11) - 0.5) * (0.12 if s['shell'] == 0 else 0.26))
        y_scale = 0.20 if s['shell'] == 0 else 0.055
        s['arm'] = arm
        s['r'] = round(radius / _MG_R, 4)
        s['x'] = round(math.cos(theta) * radius, 2)
        s['z'] = round(math.sin(theta) * radius, 2)
        s['y'] = round(
            _mg_gauss(h, 13) * _MG_R * y_scale * math.exp(-rr * 1.1)
            + (_mg_gauss(h, 17) * _MG_R * 0.05 if s['shell'] == 0 else 0), 2)

    # 4) 消息层
    messages = []
    for i, m in enumerate(messages_raw):
        h = _mg_hash(f"{m.get('key')}:{m.get('at')}:{i}")
        rr = 0.30 + (_mg_u01(h, 2) ** 0.55) * 0.76
        arm = int(math.floor(_mg_u01(h, 5) * _MG_ARMS)) % _MG_ARMS
        theta = (arm / _MG_ARMS) * math.pi * 2 - 2.6 * math.log(rr * 6 + 1) + (_mg_u01(h, 9) - 0.5) * 1.35
        radius = _MG_R * rr
        at = int(m.get('at') or 0) or now_ms
        age_days = max(0, (now_ms - at) / 86400000.0)
        messages.append({
            'id': m.get('id', f'm{i}'), 'key': str(m.get('key', 'chat')),
            'at': at, 'self': bool(m.get('self')), 'text': str(m.get('text') or '')[:60],
            'source': m.get('source', 'jingent'),
            'x': round(math.cos(theta) * radius, 1),
            'y': round(_mg_gauss(h, 13) * _MG_R * 0.075, 1),
            'z': round(math.sin(theta) * radius, 1),
            'tau': round(24 + _mg_u01(h, 15) * 12, 1),
            'ageDays': round(age_days, 2),
        })

    # 5) meta
    counts = {}
    for s in stars:
        counts[s['kind']] = counts.get(s['kind'], 0) + 1
    by_source = {}
    for s in stars + messages:
        by_source[s['source']] = by_source.get(s['source'], 0) + 1
    memory_n = sum(1 for s in stars if s['kind'] != 'diary')
    diary_n = sum(1 for s in stars if s['kind'] == 'diary')
    avg = sum(s['strength'] for s in stars) / max(1, len(stars))
    return {
        'meta': {
            'generatedAt': now_ms, 'radius': _MG_R, 'arms': _MG_ARMS,
            'total': len(stars), 'pinned': sum(1 for s in stars if s['pin']),
            'messages': len(messages), 'counts': counts,
            'sources': {'memory': memory_n, 'diary': diary_n, 'message': len(messages), 'bySource': by_source},
            'avgStrength': round(avg, 3),
        },
        'stars': stars, 'messages': messages, 'links': [],
    }


@router.get("/chat/memory", summary="记忆银河页", include_in_schema=False)
def memory_galaxy_page(request: Request):
    return _templates_ref.TemplateResponse(name="memory_galaxy.html", request=request)


@router.get("/chat/memory/api/data", summary="记忆银河数据", include_in_schema=False)
def memory_galaxy_data(
        request: Request,
        user_id: int = Depends(verify_token),
        db: Session = Depends(get_db),
):
    """把当前用户的记忆 + 对话消息画成银河。只读，不写库。"""
    now_ms = int(time.time() * 1000)

    # 记忆：global → 身份核心；detail → 按分类映射类型
    mems = db.query(Memory).filter(Memory.user_id == user_id).order_by(Memory.id.desc()).limit(500).all()
    stars_raw = []
    for m in mems:
        if m.type == 'global':
            raw_kind = 'soul'
            pin = True
        else:
            raw_kind = _memory_to_raw_kind(m.category)
            pin = False
        content = (m.content or '').strip()
        if not content:
            continue
        stars_raw.append({
            'id': f'mg-{m.id}',
            'rawKind': raw_kind,
            'weight': max(1.0, min(4.0, round((m.importance or 0.5) * 4, 2))),
            'at': _mg_ts(m.created_at),
            'lastHitAt': _mg_ts(m.last_recalled_at),
            'pin': pin,
            'title': content[:60],
            'text': content[:420],
            'tags': [m.category] if m.category else [],
            'source': 'jingent',
        })

    # 消息：最近 2000 条对话
    msgs = db.query(Message).filter(Message.user_id == user_id).order_by(Message.id.desc()).limit(2000).all()
    messages_raw = []
    for m in reversed(msgs):
        text = (m.content or '').replace('\n', ' ').strip()
        if not text:
            continue
        messages_raw.append({
            'id': f'mm-{m.id}',
            'key': f'session-{m.session_id}',
            'at': _mg_ts(m.created_at),
            'self': m.role == 'user',
            'text': text[:60],
            'source': 'jingent',
        })

    return build_memory_galaxy(stars_raw, messages_raw, now_ms)


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

    # 解析有效角色 ID（记忆/向量隔离用）
    try:
        from app.core import characters as charsvc
        active_cid = chat_request.character_id or charsvc.get_current_character_id(user_id) or "maid"
    except Exception:
        active_cid = chat_request.character_id or "maid"

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

    # 用户 AI 配置（数据库持久化，.env 打底；前端本次传参可再覆盖）
    from app.api.ai_config_routes import get_user_ai_config
    user_ai_cfg = get_user_ai_config(db, user_id) if user_id else {}

    # 对话 LLM 配置优先级：前端实时传参 > 数据库用户配置 > .env
    _req_llm = chat_request.llm or {}
    _db_llm = (user_ai_cfg or {}).get("llm") or {}
    _llm_cfg = {
        "model": (_req_llm.get("model") or "").strip() or (_db_llm.get("model") or "").strip(),
        "base_url": (_req_llm.get("base_url") or "").strip() or (_db_llm.get("base_url") or "").strip(),
        "api_key": (_req_llm.get("api_key") or "").strip() or (_db_llm.get("api_key") or "").strip(),
    }
    model_name, base_url, api_key = resolve_llm_config(_llm_cfg)
    model = init_chat_model(
        model=model_name,
        model_provider="openai",
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
    )

    # 图片解析配置：注入用户数据库配置（工具内部 .env 打底，用户覆盖）
    try:
        from app.tools.tool_Image_parsing import set_user_image_vl_config
        set_user_image_vl_config(user_ai_cfg.get("image_vl") or None)
    except Exception as e:
        logger.warning("[image_vl] 注入用户配置失败: %s", e)

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

    memory_prompt = build_memory_prompt(user_id, db, chat_request.chat_type, character_id=active_cid, query=chat_request.newMessage)
    if memory_prompt:
        final_system_prompt = memory_prompt + "\n\n" + final_system_prompt

    # RAG：主对话注入语义检索到的历史对话（新建会话不注入）
    if chat_request.chat_type == "main" and user_id:
        try:
            from app.core.rag import get_rag_store
            _req_emb = chat_request.embedding or {}
            _db_emb = (user_ai_cfg or {}).get("embedding") or {}
            _emb_cfg = {
                "base_url": (_req_emb.get("base_url") or "").strip() or (_db_emb.get("base_url") or "").strip(),
                "model": (_req_emb.get("model") or "").strip() or (_db_emb.get("model") or "").strip(),
                "api_key": (_req_emb.get("api_key") or "").strip() or (_db_emb.get("api_key") or "").strip(),
            }
            rag_cfg = resolve_embedding_config(_emb_cfg)
            rag_hits = get_rag_store().search(user_id, chat_request.newMessage, k=5, embedding_cfg=rag_cfg,
                                              character_id=active_cid)
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

    # 输入 token 估算：system prompt + 记忆 + 历史 + 新消息
    _tokens_in = estimate_tokens(final_system_prompt) + estimate_tokens(chat_request.newMessage)
    for _h in ai_context:
        _tokens_in += estimate_tokens(getattr(_h, "message", "") or "")
    _request_id = http_request.scope.get("request_id", "")

    async def generate():
        buffer = ""          # 流式缓冲：跨 chunk 累积，检测 ||| 分隔符
        parts: List[str] = []  # 拆分后的多条回复

        # 桌宠联动：开始思考
        _broadcast_pet({"t": "turn-start"})

        # SSE 统一用 JSON 帧，避免回复文本含换行时破坏 SSE 协议导致前端丢行/截断。
        # 帧类型：{t:"delta",text} / {t:"split"} / {t:"history",history} / {t:"done"}
        def frame(obj) -> str:
            return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

        async for msg_chunk, metadata in agent.astream(
                {"messages": messages},
                stream_mode="messages",
        ):
            # 工具返回（ToolMessage）是 Agent 中间过程，不推给用户；
            # 只收集 AI 文本，最终回复由 LLM 整合后给出。
            if isinstance(msg_chunk, ToolMessage):
                continue
            content = msg_chunk.content
            # 多模态/复合 chunk 的 content 可能是 list，只取 text 块
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, str):
                        text_parts.append(block)
                    elif isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", "") or "")
                content = "".join(text_parts)
            if not content:
                continue

            buffer += content
            # 检测「|||」分隔符：真人连发多条消息
            while "|||" in buffer:
                idx = buffer.index("|||")
                segment = buffer[:idx]
                buffer = buffer[idx + 3:]
                parts.append(segment)
                if segment:
                    # 桌宠联动：逐字输出 → 嘴巴动
                    _broadcast_pet({"t": "delta", "text": segment})
                    yield frame({"t": "delta", "text": segment})
                # 通知前端：本条结束，开新气泡
                yield frame({"t": "split"})

        # flush 剩余缓冲
        if buffer:
            parts.append(buffer)
            _broadcast_pet({"t": "delta", "text": buffer})
            yield frame({"t": "delta", "text": buffer})

        # 清理空段；全部为空时保留一条空回复，避免历史丢失
        parts = [p.strip() for p in parts if p.strip()]
        if not parts:
            parts = [""]
        full_ai_reply = "".join(parts)

        # 输出 token 估算 + 异步写回 request_logs（关联 request_id）
        if _request_id:
            _record_chat_tokens(_request_id, _tokens_in, estimate_tokens(full_ai_reply))

        ai_messages = [ChatMessage(role="ai", message=p, created_at=_now_iso()) for p in parts]
        final_history = full_history + ai_messages

        yield frame({"t": "history", "history": [m.model_dump() for m in final_history]})
        yield frame({"t": "done"})

        # 桌宠联动：结束 → 完成
        _broadcast_pet({"t": "turn-end", "status": "success"})

        # 每累计 20 轮后台抽取记忆（不阻塞 SSE）
        if user_id and full_ai_reply:
            _schedule_memory_extract(
                user_id,
                base_url, model_name, api_key,
                character_id=active_cid,
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

    # 解析有效角色 ID（记忆/向量隔离用）
    try:
        from app.core import characters as charsvc
        active_cid = chat_request.character_id or charsvc.get_current_character_id(user_id) or "maid"
    except Exception:
        active_cid = chat_request.character_id or "maid"

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

    # 用户 AI 配置（数据库持久化，.env 打底；前端本次传参可再覆盖）
    from app.api.ai_config_routes import get_user_ai_config
    user_ai_cfg = get_user_ai_config(db, user_id) if user_id else {}

    _req_llm = chat_request.llm or {}
    _db_llm = (user_ai_cfg or {}).get("llm") or {}
    _llm_cfg = {
        "model": (_req_llm.get("model") or "").strip() or (_db_llm.get("model") or "").strip(),
        "base_url": (_req_llm.get("base_url") or "").strip() or (_db_llm.get("base_url") or "").strip(),
        "api_key": (_req_llm.get("api_key") or "").strip() or (_db_llm.get("api_key") or "").strip(),
    }
    model_name, base_url, api_key = resolve_llm_config(_llm_cfg)
    model = init_chat_model(
        model=model_name,
        model_provider="openai",
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
    )

    # 图片解析配置：注入用户数据库配置
    try:
        from app.tools.tool_Image_parsing import set_user_image_vl_config
        set_user_image_vl_config(user_ai_cfg.get("image_vl") or None)
    except Exception as e:
        logger.warning("[image_vl] 注入用户配置失败: %s", e)

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

    memory_prompt = build_memory_prompt(user_id, db, chat_request.chat_type, character_id=active_cid, query=chat_request.newMessage)
    if memory_prompt:
        final_system_prompt = memory_prompt + "\n\n" + final_system_prompt

    # RAG：主对话注入语义检索到的历史对话（新建会话不注入）
    if chat_request.chat_type == "main" and user_id:
        try:
            from app.core.rag import get_rag_store
            _req_emb = chat_request.embedding or {}
            _db_emb = (user_ai_cfg or {}).get("embedding") or {}
            _emb_cfg = {
                "base_url": (_req_emb.get("base_url") or "").strip() or (_db_emb.get("base_url") or "").strip(),
                "model": (_req_emb.get("model") or "").strip() or (_db_emb.get("model") or "").strip(),
                "api_key": (_req_emb.get("api_key") or "").strip() or (_db_emb.get("api_key") or "").strip(),
            }
            rag_cfg = resolve_embedding_config(_emb_cfg)
            rag_hits = get_rag_store().search(user_id, chat_request.newMessage, k=5, embedding_cfg=rag_cfg,
                                              character_id=active_cid)
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
    # 输入 token 估算：system prompt + 历史 + 新消息
    _tokens_in = estimate_tokens(final_system_prompt) + estimate_tokens(chat_request.newMessage)
    for _h in ai_context:
        _tokens_in += estimate_tokens(getattr(_h, "message", "") or "")
    _request_id = http_request.scope.get("request_id", "")

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

        # 输出 token 估算 + 异步写回 request_logs（关联 request_id）
        if _request_id:
            _record_chat_tokens(_request_id, _tokens_in, estimate_tokens(ai_reply or ""))

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

        # 每累计 20 轮后台抽取记忆（不阻塞响应）
        if user_id and ai_reply:
            _schedule_memory_extract(
                user_id,
                base_url, model_name, api_key,
                character_id=active_cid,
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

        # 主对话按灵魂隔离：解析 character_id（缺省回退用户当前绑定角色）
        resolved_cid = None
        if chat_type == "main":
            resolved_cid = request.character_id
            if not resolved_cid:
                try:
                    from app.core import characters as charsvc
                    resolved_cid = charsvc.get_current_character_id(user_id)
                except Exception:
                    resolved_cid = None
            # 记录会话绑定的灵魂
            session.character_id = resolved_cid

        # 原子化：同步 Message 表。
        # 主对话按灵魂隔离：只删除/重写「当前灵魂」的消息，其他灵魂的消息保留。
        if chat_type == "main" and resolved_cid:
            db.query(Message).filter(
                Message.session_id == session.id,
                Message.character_id == resolved_cid,
            ).delete()
        else:
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
            # 主对话消息打上灵魂标记
            if chat_type == "main" and resolved_cid:
                msg_kwargs["character_id"] = resolved_cid
            # 保留每条消息原始时间戳；缺失时才用 DB 列的 default（避免覆盖为 NULL/同一时刻）
            created_at = _parse_dt(m.get("created_at"))
            if created_at is not None:
                msg_kwargs["created_at"] = created_at
            db.add(Message(**msg_kwargs))

        db.commit()

        # RAG：主对话消息写入向量库（后台线程，不阻塞保存；独立 session 避免线程问题，按角色隔离）
        if chat_type == "main":
            _schedule_rag_write(session.id, user_id, character_id=resolved_cid or "maid")
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
    # 主对话按灵魂隔离：读取时用用户当前绑定角色过滤
    main_cid = None
    try:
        from app.core import characters as charsvc
        main_cid = charsvc.get_current_character_id(user_id)
    except Exception:
        main_cid = None

    def _session_messages(session) -> list:
        """从 Message 表重组消息（原子化路径），回退旧 JSON。

        reply_to 只存在于 session.messages JSON（Message 表未存），
        重组时按顺序从 JSON 回填，保证引用块与跳转不丢。
        主对话（main）按 character_id 过滤，实现灵魂间历史隔离。
        """
        legacy = session.messages or []
        # 只保留有 message 的项，与 ai_savaToDb 写 Message 表时「跳过空消息」保持一致，避免下标错位
        legacy_reply = [
            m.get("reply_to")
            for m in legacy
            if isinstance(m, dict) and m.get("message")
        ]
        q = db.query(Message).filter(Message.session_id == session.id)
        # 主对话按灵魂过滤
        if (session.chat_type or "") == "main" and main_cid:
            q = q.filter(Message.character_id == main_cid)
        rows = q.order_by(Message.id.asc()).all()
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
        # 主对话按灵魂过滤后为空：直接返回空列表，不回退旧 JSON。
        # 旧 JSON（session.messages）只存了「最后一次写入的灵魂」的 chatData，
        # 回退会读到别的灵魂的对话，破坏隔离。
        if (session.chat_type or "") == "main" and main_cid:
            return []
        # 回退：旧 JSON（仅新建会话 / 未迁移历史遗留）
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
