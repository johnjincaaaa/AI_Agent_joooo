"""
聊天相关路由和模型 — extracted from main.py.

路径保持不变：无 prefix，直接 /, /chat, /ai/*
"""
import json
import logging
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, HTTPException, Request, UploadFile, File, Query,
)
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

import config
from config import (
    ALLOWED_IMAGE_TYPES, ALLOWED_DOCUMENT_TYPES, ALLOWED_FILE_EXTENSIONS,
    MAX_IMAGE_SIZE, MAX_DOCUMENT_SIZE, UPLOAD_DIR, SYSTEM_PROMPT,
    MODEL, DASHSCOPE_URL, DASHSCOPE_API_KEY,
)
from sqlOrm import get_db, ChatSession
from token_utils import verify_token, get_optional_user_id
from rate_limit import check_anonymous_rate_limit, get_anonymous_remaining
import tools
from tools.skills_registry import get_skill_catalog, resolve_tools
from services import promo

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


# ==================================================================
# Pydantic 模型
# ==================================================================

class ChatMessage(BaseModel):
    role: str
    message: str


class ChatRequest(BaseModel):
    history: List[ChatMessage]
    newMessage: str
    open_online: bool = False
    enabled_skills: List[str] = []
    image_paths: List[str] = []
    document_paths: List[str] = []
    lang: str = "zh"
    scene: Optional[str] = None


class ChatDbRequest(BaseModel):
    chat_data: List[ChatMessage]
    create_time: int
    session_name: str


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


def build_system_prompt(lang: str = "zh", scene: Optional[str] = None) -> str:
    is_en = (lang or "zh").lower().startswith("en")

    if scene and scene in config.SCENE_PRESETS:
        preset = config.SCENE_PRESETS[scene]
        return preset["system_prompt_en"] if is_en else preset["system_prompt_zh"]

    if is_en:
        return "You are a helpful assistant. Always respond in English."
    return SYSTEM_PROMPT


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


# ==================================================================
# 技能 & 场景
# ==================================================================

@router.get("/ai/skills", summary="获取可用技能列表")
def list_skills():
    return {"code": 200, "skills": get_skill_catalog()}


@router.get("/ai/skills/market", summary="获取技能市场列表")
def list_skill_market():
    from tools.skills_registry import get_all_skills
    return {"code": 200, **get_all_skills()}


@router.post("/ai/skills/preview", summary="预览技能包（解析zip）")
async def preview_skill_package(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        from tools.skill_package_manager import parse_skill_zip
        result = parse_skill_zip(contents)
        return {"code": 200 if result["valid"] else 400, **result}
    except Exception as e:
        return {"code": 500, "error": f"上传失败: {str(e)}"}


@router.post("/ai/skills/install", summary="安装技能包")
async def install_skill_package(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        from tools.skill_package_manager import install_skill
        result = install_skill(contents)
        if result["success"]:
            return {"code": 200, "skill": result["skill"]}
        return {"code": 400, "error": result["error"]}
    except Exception as e:
        return {"code": 500, "error": f"安装失败: {str(e)}"}


@router.get("/ai/skills/installed", summary="获取已安装的自定义技能列表")
def list_installed_skills_api():
    from tools.skill_package_manager import list_installed_skills
    return {"code": 200, "skills": list_installed_skills()}


@router.delete("/ai/skills/installed/{skill_id}", summary="卸载已安装的自定义技能")
def uninstall_skill_api(skill_id: str):
    from tools.skill_package_manager import uninstall_skill
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
):
    remaining = ensure_chat_access(http_request, user_id)

    full_history = chat_request.history.copy()
    full_history.append(ChatMessage(role='user', message=chat_request.newMessage))
    ai_context = full_history[-50:]

    model = init_chat_model(
        model=MODEL,
        model_provider="openai",
        base_url=DASHSCOPE_URL,
        api_key=DASHSCOPE_API_KEY,
        temperature=temperature,
    )
    enabled_skills = resolve_enabled_skills(
        chat_request.enabled_skills,
        chat_request.image_paths,
        chat_request.document_paths,
    )
    tool_list = build_tool_list(chat_request.open_online, enabled_skills)

    from tools.skills_registry import get_prompt_skill_system_prompt
    from tools.skill_package_manager import get_installed_skill_system_prompt
    base_system_prompt = build_system_prompt(chat_request.lang, chat_request.scene)
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
        full_ai_reply = ""

        async for msg_chunk, metadata in agent.astream(
                {"messages": messages},
                stream_mode="messages",
        ):
            if msg_chunk.content:
                content = msg_chunk.content
                full_ai_reply += content
                yield f"data: {content}\n\n"

        ai_message = ChatMessage(role="ai", message=full_ai_reply)
        final_history = full_history + [ai_message]

        yield f"data: [HISTORY] {json.dumps([m.model_dump() for m in final_history], ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

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
):
    ensure_chat_access(http_request, user_id)

    full_history = chat_request.history.copy()
    full_history.append(ChatMessage(role='user', message=chat_request.newMessage))
    ai_context = full_history[-50:]

    model = init_chat_model(
        model=MODEL,
        model_provider="openai",
        base_url=DASHSCOPE_URL,
        api_key=DASHSCOPE_API_KEY,
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

    from tools.skills_registry import get_prompt_skill_system_prompt
    from tools.skill_package_manager import get_installed_skill_system_prompt
    base_system_prompt = build_system_prompt(chat_request.lang, chat_request.scene)
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
    try:
        result = agent.invoke({"messages": messages})
        for msg in result["messages"]:
            if msg.type == "tool":
                logger.info(f"[调用工具] {msg.name} | {msg.content}")
            elif msg.type == "ai" and msg.content:
                logger.info(f"\n最终AI回答: {msg.content}")
        ai_reply = result["messages"][-1].content

        final_history = full_history + [{"role": "ai", "message": ai_reply}]

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
             description=""" 按 【user_id + 秒级时间】 查询,数据更新或创建""")
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
        if existing_session:
            existing_session.messages = [m.model_dump() for m in request.chat_data]
            existing_session.session_name = request.session_name

        else:
            new_session = ChatSession(
                user_id=user_id,
                session_name=request.session_name,
                session_time=session_time,
                messages=[m.model_dump() for m in request.chat_data]
            )
            db.add(new_session)

        db.commit()
        return {"code": 200, "msg": "保存/更新成功"}

    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={"code": 500, "msg": f"异常：{str(error)}"}
        )


@router.get('/ai/chat/history', summary='读取数据库chat_sessions中的messages',
            description="""需要加密 ！！ """)
def ai_history(
        user_id: int = Depends(verify_token),
        session_time: int = Query(None),
        is_Load_All: bool = Query(False),
        db: Session = Depends(get_db)
):
    if is_Load_All:
        existing_sessions = db.query(ChatSession).filter(
            ChatSession.user_id == user_id,
        ).order_by(ChatSession.session_time.desc()).all()
        try:
            if existing_sessions:
                result = []
                for item in existing_sessions:
                    result.append({
                        "session_name": item.session_name,
                        "session_time": item.session_time,
                        "messages": item.messages
                    })
                return {
                    "code": 200,
                    "chat_sessions": result,
                }
            else:
                raise HTTPException(
                    status_code=500,
                    detail={"messages": None, "session_name": None}
                )
        except Exception as error:
            raise HTTPException(
                status_code=500,
                detail={"code": 500, "msg": f"异常：{str(error)}"}
            )

    else:
        existing_session = db.query(ChatSession).filter(
            ChatSession.user_id == user_id,
            ChatSession.session_time == session_time
        ).first()

        try:
            if existing_session:
                return {
                    "code": 200,
                    "messages": existing_session.messages,
                    "session_name": existing_session.session_name,
                }
            else:
                raise HTTPException(
                    status_code=500,
                    detail={"messages": None, "session_name": None}
                )
        except Exception as error:
            raise HTTPException(
                status_code=500,
                detail={"code": 500, "msg": f"异常：{str(error)}"}
            )


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
