from sqlalchemy.orm import Session
import uvicorn
from fastapi import FastAPI, Request, Depends, HTTPException, Query, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
import json
from pydantic import BaseModel
from typing import List, Optional
import logging
import uuid
from pathlib import Path

import config

logger = logging.getLogger("uvicorn.info")

from config import *
from token_utils import (
    create_access_token, verify_token, get_optional_user_id,
    create_admin_token, verify_admin_token,
)
from password_utils import hash_password, verify_password, needs_rehash
from rate_limit import check_anonymous_rate_limit, get_anonymous_remaining
from services import promo
# 提前引入 ORM（get_db 等），供靠前定义的路由用作默认参数（默认值在定义时求值）
from sqlOrm import *
import tools
from tools.skills_registry import get_skill_catalog, resolve_tools
from services.job_mock_data import RESUME_TEMPLATES, MOCK_JOBS, match_jobs

try:
    from langchain.chat_models import init_chat_model
    from langchain.agents import create_agent
    from langchain.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
except ModuleNotFoundError as e:
    print(e)

# 初始化 FastAPI 应用
app = FastAPI(
    title="有料 AI",
    description="一个致力于取悦自我的ai应用",
    version="1.0",

)
app.mount("/static", StaticFiles(directory="static"), name="static")  # ✅ 静态文件统一配置（全局只需这一句）
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
templates = Jinja2Templates(directory="templates")  # 自动找 HTML

# 静态资源版本号：附加到 css/js 链接后（?v=），改动后浏览器会自动拉新，避免缓存旧文件。
# 用启动时间戳，每次重启服务即刷新缓存；生产可改成固定版本号或 git commit。
import time as _time
ASSET_VERSION = str(int(_time.time()))
templates.env.globals["ASSET_VERSION"] = ASSET_VERSION

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
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_DOCUMENT_SIZE = 20 * 1024 * 1024  # 20MB

# 允许跨域（让你的 HTML 页面可以调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------- 聊天页 -------------------
# 根路径 "/" 和 "/chat" 都进聊天页，这样域名不带 /chat 也能直接访问
@app.get("/", summary="首页（等同聊天页）", include_in_schema=False)
@app.get("/chat", summary="聊天页",
         description="启动入口，返回html")
def chat_page(request: Request, db: Session = Depends(get_db)):
    # 访问埋点（PV/UV）——失败绝不影响页面返回
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
    return templates.TemplateResponse(name="ai.html", request=request)


# 定义消息结构
class ChatMessage(BaseModel):
    role: str  # user / ai
    message: str


# 前端传过来的结构
class ChatRequest(BaseModel):
    """
    {
      "history": [
        {"role": "user", "message": "你好"}, === ChatMessage
        {"role": "ai", "message": "你好！"},
        ...
      ],
      "newMessage": "我最新说的话",
      open_online: False # 全局一键联网开关


    }
    """
    history: List[ChatMessage]  # 完整历史
    newMessage: str  # 最新一条消息
    open_online: bool = False  # 全局一键联网开关
    enabled_skills: List[str] = []  # 前端选中的技能 id 列表
    image_paths: List[str] = []  # 用户粘贴/上传图片的服务端路径
    document_paths: List[str] = []  # 用户上传文档的服务端路径
    lang: str = "zh"  # 界面语言，AI 回复语言随之切换（zh / en）
    scene: Optional[str] = None  # 场景模板 id（chat / office / study / life），None 表示通用模式


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
    """根据界面语言和场景模板返回系统提示词，控制 AI 回复语言和风格。"""
    is_en = (lang or "zh").lower().startswith("en")

    # 如果指定了场景模板，优先使用场景对应的系统提示词
    if scene and scene in config.SCENE_PRESETS:
        preset = config.SCENE_PRESETS[scene]
        return preset["system_prompt_en"] if is_en else preset["system_prompt_zh"]

    # 默认通用模式
    if is_en:
        return "You are a helpful assistant. Always respond in English."
    return SYSTEM_PROMPT


def build_tool_list(open_online: bool, enabled_skills: Optional[List[str]] = None):
    tool_list = list(config.TOOL_LIST)
    tool_list.extend(resolve_tools(enabled_skills or []))
    if open_online:
        tool_list.extend([tools.online, tools.online_intensive])
    return tool_list


@app.get("/ai/skills", summary="获取可用技能列表")
def list_skills():
    return {"code": 200, "skills": get_skill_catalog()}


@app.get("/ai/skills/market", summary="获取技能市场列表")
def list_skill_market():
    """返回技能市场所有技能（已安装+市场可安装）。"""
    from tools.skills_registry import get_all_skills
    return {"code": 200, **get_all_skills()}


@app.post("/ai/skills/preview", summary="预览技能包（解析zip）")
async def preview_skill_package(file: UploadFile = File(...)):
    """上传技能包 zip，预览技能信息（不安装）。"""
    try:
        contents = await file.read()
        from tools.skill_package_manager import parse_skill_zip
        result = parse_skill_zip(contents)
        return {"code": 200 if result["valid"] else 400, **result}
    except Exception as e:
        return {"code": 500, "error": f"上传失败: {str(e)}"}


@app.post("/ai/skills/install", summary="安装技能包")
async def install_skill_package(file: UploadFile = File(...)):
    """上传并安装技能包 zip。"""
    try:
        contents = await file.read()
        from tools.skill_package_manager import install_skill
        result = install_skill(contents)
        if result["success"]:
            return {"code": 200, "skill": result["skill"]}
        return {"code": 400, "error": result["error"]}
    except Exception as e:
        return {"code": 500, "error": f"安装失败: {str(e)}"}


@app.get("/ai/skills/installed", summary="获取已安装的自定义技能列表")
def list_installed_skills_api():
    """返回所有已安装的自定义技能（通过 zip 导入的）。"""
    from tools.skill_package_manager import list_installed_skills
    return {"code": 200, "skills": list_installed_skills()}


@app.delete("/ai/skills/installed/{skill_id}", summary="卸载已安装的自定义技能")
def uninstall_skill_api(skill_id: str):
    """卸载指定的已安装技能。"""
    from tools.skill_package_manager import uninstall_skill
    if uninstall_skill(skill_id):
        return {"code": 200, "message": "卸载成功"}
    return {"code": 404, "error": "技能不存在"}


@app.get("/ai/scenes", summary="获取大众场景模板列表（含快捷模板）")
def list_scenes():
    """返回四大大众场景模板：日常闲聊、办公文案、学习答疑、生活解惑，含每个场景的快捷模板。"""
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


@app.get("/ai/scenes/{scene_id}/templates", summary="获取指定场景的快捷模板详情")
def get_scene_templates(scene_id: str):
    """返回指定场景的所有快捷模板（含完整 prompt）。"""
    preset = config.SCENE_PRESETS.get(scene_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Scene not found")
    templates = preset.get("quick_templates", [])
    return {"code": 200, "templates": templates}


@app.post("/ai/upload-image", summary="上传聊天图片")
async def upload_image(
        http_request: Request,
        file: UploadFile = File(...),
        user_id: Optional[int] = Depends(get_optional_user_id),
):
    result = await _handle_file_upload(http_request, file, user_id)
    if result["kind"] != "image":
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "请使用文档上传接口上传非图片文件"})
    return result


@app.post("/ai/upload-file", summary="上传聊天附件")
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


def ensure_chat_access(http_request: Request, user_id: Optional[int]) -> Optional[int]:
    """已登录用户不限流，返回 None；未登录用户消耗一次并返回今日剩余次数。"""
    if user_id is None:
        return check_anonymous_rate_limit(http_request)
    return None


# 未登录体验剩余次数（前端用于展示「今日还剩 N 次」并做用完拦截）
@app.get("/ai/quota", summary="查询未登录用户今日免费体验剩余次数")
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


# ==================== 改造后的 流式+历史 接口 ====================
@app.post("/ai/chatStream")
async def chat_stream(
        chat_request: ChatRequest,
        http_request: Request,
        temperature: float = 0.7,
        user_id: Optional[int] = Depends(get_optional_user_id),
):
    """SSE流式输出 + 最终返回完整对话历史"""
    remaining = ensure_chat_access(http_request, user_id)

    # 1. 构建历史（动态记忆：默认 50 轮上下文）
    full_history = chat_request.history.copy()
    full_history.append(ChatMessage(role='user', message=chat_request.newMessage))
    ai_context = full_history[-50:]

    # 2. 初始化模型（和原来完全一样）
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

    # 合并提示词技能的系统提示词
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

    # 3. 格式化消息（含图片路径提示）
    messages = build_agent_messages(
        ai_context,
        chat_request.image_paths,
        chat_request.document_paths,
    )

    # ==================== 核心改造：流式输出 + 收集完整回答 ====================
    async def generate():
        # 新增：用于收集AI完整的回答内容
        full_ai_reply = ""

        # 1. 流式输出每一段文字
        async for msg_chunk, metadata in agent.astream(
                {"messages": messages},
                stream_mode="messages",
        ):
            if msg_chunk.content:
                content = msg_chunk.content
                full_ai_reply += content  # 拼接完整回答
                yield f"data: {content}\n\n"  # 实时流式输出

        # 2. AI回答完毕，构建完整历史
        # 格式化为标准ChatMessage结构
        ai_message = ChatMessage(role="ai", message=full_ai_reply)
        final_history = full_history + [ai_message]

        # 3. 通过SSE发送【完整历史数据】给前端（特殊标记）
        yield f"data: [HISTORY] {json.dumps([m.model_dump() for m in final_history], ensure_ascii=False)}\n\n"

        # 4. 发送结束标记
        yield "data: [DONE]\n\n"

    # 返回SSE流式响应；未登录用户回传今日剩余次数，供前端展示与用完拦截
    headers = {}
    if remaining is not None:
        headers["X-Anon-Remaining"] = str(remaining)
        headers["Access-Control-Expose-Headers"] = "X-Anon-Remaining"
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers=headers,
    )

# ------------------- 主接口：AI 聊天 -------------------
@app.post("/ai/chat", summary='AI 聊天'
    , description="""构建完整对话历史,取最后20条传给 AI，返回完整新历史给前端，前端同步内存""")
def ai_chat(
        chat_request: ChatRequest,
        http_request: Request,
        temperature: float = 0.7,
        user_id: Optional[int] = Depends(get_optional_user_id),
):
    ensure_chat_access(http_request, user_id)

    # ==========================================
    # 1. 构建完整对话历史 = 历史对话 + 最新发送
    # ==========================================
    full_history = chat_request.history.copy()
    full_history.append(ChatMessage(role='user', message=chat_request.newMessage))
    # ==========================================
    # 2. 【关键】只取最后 50 条给 AI（动态记忆）
    # ==========================================
    ai_context = full_history[-50:]  # 取最后50条！

    # ==========================================
    # 3. 把 ai_context 传给 AI
    # ==========================================
    model = init_chat_model(
        model=MODEL,
        model_provider="openai",  # 走openai兼容模式
        base_url=DASHSCOPE_URL,
        api_key=DASHSCOPE_API_KEY,
        temperature=temperature,
        # num_gpu=-1
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

    # 合并提示词技能的系统提示词
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

        # ==========================================
        # 4. 返回【完整对话】
        # ==========================================
        # 完整新历史 = (旧历史 + 用户新消息) + AI回复
        final_history = full_history + [{"role": "ai", "message": ai_reply}]

        # ==========================================
        # 5. 返回完整新历史给前端，前端同步内存
        # ==========================================
        return {
            "code": 200,
            "content": ai_reply,
            "new_history": final_history  # 前端用这个覆盖 chatData
        }
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail={"code": 500, "msg": f"异常：{str(error)}"}
        )


class ChatDbRequest(BaseModel):
    chat_data: List[ChatMessage]
    create_time: int
    session_name: str


# ------------------- 接口：接收数据并存入数据库 -------------------
from sqlOrm import *


@app.post('/ai/chat/savaToDb', summary='接收数据并存入数据库',
          description=""" 按 【user_id + 秒级时间】 查询,数据更新或创建""")
def ai_savaToDb(
        request: ChatDbRequest,
        db: Session = Depends(get_db),
        user_id: int = Depends(verify_token)
):
    # 转化为用户凭证
    # user_id = 1
    session_time = request.create_time

    # ========================
    # 按 【user_id + 秒级时间】 查询
    # ========================
    existing_session = db.query(ChatSession).filter(
        ChatSession.user_id == user_id,
        ChatSession.session_time == session_time
    ).first()

    try:
        if existing_session:
            # 更新
            existing_session.messages = [m.model_dump() for m in request.chat_data]
            existing_session.session_name = request.session_name

        else:
            # 插入
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


# ------------------- 接口：读取数据库chat_sessions中的messages ------------------
@app.get('/ai/chat/history', summary='读取数据库chat_sessions中的messages',
         description="""需要加密 ！！ """)
def ai_history(
        # 转化为用户凭证，由前端传入，后端校验
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
                # ✅ 把对象转成字典列表（前端能识别）
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


# ------------------- 接口：重命名会话 -------------------
class ChatRenameRequest(BaseModel):
    session_time: int
    session_name: str


@app.post('/ai/chat/rename', summary='重命名会话')
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


# ------------------- 接口：删除会话 -------------------
@app.delete('/ai/chat/delete', summary='删除会话')
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


# ------------------- 无代码工作流 -------------------
class WorkflowNode(BaseModel):
    id: str
    type: str  # start / end / ai_chat / code / condition / template / user_input / loop / merge
    x: float
    y: float
    data: dict = {}

class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str

class WorkflowPayload(BaseModel):
    name: str = "未命名工作流"
    nodes: List[WorkflowNode] = []
    edges: List[WorkflowEdge] = []
    initial_input: str = ""  # 初始输入


@app.get("/workflow", summary="无代码工作流编辑器")
def workflow_page(request: Request):
    return templates.TemplateResponse(name="workflow.html", request=request)


@app.get("/ai/workflows", summary="获取工作流列表")
def get_workflows(user_id: int = Depends(verify_token)):
    return {"code": 200, "workflows": []}


def _topo_sort(nodes_dict, edges):
    """拓扑排序，返回节点ID顺序列表"""
    in_degree = {nid: 0 for nid in nodes_dict}
    adj = {nid: [] for nid in nodes_dict}
    for e in edges:
        src, tgt = e.source, e.target
        if src in nodes_dict and tgt in nodes_dict:
            adj[src].append(tgt)
            in_degree[tgt] = in_degree.get(tgt, 0) + 1
    queue = [nid for nid, d in in_degree.items() if d == 0]
    result = []
    while queue:
        nid = queue.pop(0)
        result.append(nid)
        for tgt in adj[nid]:
            in_degree[tgt] -= 1
            if in_degree[tgt] == 0:
                queue.append(tgt)
    return result


def _get_out_edges(node_id, edges):
    """获取节点的所有出边"""
    return [e for e in edges if e.source == node_id]


@app.post("/ai/workflow/run", summary="执行工作流")
async def run_workflow(
    payload: WorkflowPayload,
    user_id: Optional[int] = Depends(get_optional_user_id),
):
    nodes = payload.nodes
    edges = payload.edges
    initial_input = payload.initial_input or ""

    if not nodes:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "工作流为空"})

    nodes_dict = {n.id: n for n in nodes}
    start_nodes = [n for n in nodes if n.type == "start"]
    end_nodes = [n for n in nodes if n.type == "end"]

    if not start_nodes:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "缺少开始节点"})

    # 执行日志
    execution_log = []
    # 每个节点的输出
    node_outputs = {}
    # 已执行节点集合
    executed = set()
    # merge 节点的待合并输入：{node_id: {source_id: output}}
    merge_pending = {}

    def log(node_id, status, msg="", output=None):
        entry = {"node_id": node_id, "status": status, "message": msg}
        if output is not None:
            entry["output"] = output
        execution_log.append(entry)
        node_outputs[node_id] = output

    def _get_upstream_outputs(node_id):
        """获取某节点所有上游的输出列表"""
        outs = []
        for e in edges:
            if e.target == node_id and e.source in node_outputs:
                outs.append(node_outputs[e.source])
        return outs

    def _get_in_degree(node_id):
        """获取某节点的入度（上游节点数）"""
        return sum(1 for e in edges if e.target == node_id)

    def _enqueue_downstream(node_id, queue, extra_input=None):
        """把下游节点加入队列；extra_input 用于 loop 循环时传递每次迭代的值"""
        for e in _get_out_edges(node_id, edges):
            tgt = e.target
            tgt_node = nodes_dict.get(tgt)
            if not tgt_node:
                continue
            # merge 节点：需要等待所有上游完成
            if tgt_node.type == "merge":
                if tgt not in merge_pending:
                    merge_pending[tgt] = {}
                # 记录这次的来源输出
                src_output = extra_input if extra_input is not None else node_outputs.get(node_id)
                merge_pending[tgt][node_id] = src_output
                # 检查是否所有上游都到齐
                in_deg = _get_in_degree(tgt)
                if len(merge_pending[tgt]) >= in_deg:
                    queue.append(tgt)
            else:
                if extra_input is not None:
                    # 把额外输入暂存到 node_outputs 中供下游读取
                    node_outputs[node_id] = extra_input
                if tgt not in executed:
                    queue.append(tgt)

    # ========== 开始执行 ==========
    start_id = start_nodes[0].id
    node_outputs[start_id] = initial_input
    log(start_id, "success", "开始执行", initial_input)
    executed.add(start_id)

    queue = []
    _enqueue_downstream(start_id, queue)

    max_steps = 200
    step = 0

    while queue and step < max_steps:
        step += 1
        node_id = queue.pop(0)
        node = nodes_dict.get(node_id)
        if not node:
            continue

        # 如果已经执行过且不是 loop（loop 允许多次执行），跳过
        if node_id in executed and node.type != "loop":
            continue

        # 获取上游输入
        upstream_outputs = _get_upstream_outputs(node_id)

        # merge 节点：合并输入
        if node.type == "merge":
            data = node.data or {}
            strategy = data.get("strategy", "concat")
            pending = merge_pending.get(node_id, {})
            all_inputs = list(pending.values()) if pending else upstream_outputs

            if strategy == "last":
                merged = all_inputs[-1] if all_inputs else ""
                msg = f"合并完成（取最新，共 {len(all_inputs)} 个输入）"
            elif strategy == "first":
                merged = all_inputs[0] if all_inputs else ""
                msg = f"合并完成（取最早，共 {len(all_inputs)} 个输入）"
            else:  # concat
                merged = "\n\n---\n\n".join([str(x) for x in all_inputs if x is not None])
                msg = f"合并完成（拼接，共 {len(all_inputs)} 个输入）"

            log(node_id, "success", msg, merged)
            executed.add(node_id)
            _enqueue_downstream(node_id, queue)
            continue

        # 取当前输入
        current_input = upstream_outputs[-1] if upstream_outputs else ""

        out_edges = _get_out_edges(node_id, edges)

        if node.type == "end":
            log(node_id, "success", "执行结束", current_input)
            executed.add(node_id)
            break

        if node.type == "ai_chat":
            data = node.data or {}
            sys_prompt = data.get("systemPrompt", "")
            temperature = float(data.get("temperature", 0.7))
            log(node_id, "running", "AI 处理中...")
            try:
                model = init_chat_model(
                    model=MODEL, model_provider="openai",
                    base_url=DASHSCOPE_URL, api_key=DASHSCOPE_API_KEY,
                    temperature=temperature,
                )
                agent = create_agent(
                    model=model,
                    system_prompt=sys_prompt or "你是有料AI，一位专业的AI助手。",
                    tools=[],
                )
                messages = [{"role": "user", "content": current_input}]
                result = agent.invoke({"messages": messages})
                ai_reply = result["messages"][-1].content
                log(node_id, "success", f"AI 回复完成（{len(ai_reply)}字）", ai_reply)
                current_input = ai_reply
            except Exception as err:
                log(node_id, "error", f"AI 调用失败: {str(err)}", current_input)

        elif node.type == "code":
            data = node.data or {}
            code_text = (data.get("code", "") or "").strip()
            log(node_id, "running", "代码执行中...")
            try:
                from tools.tool_code_sandbox import run_python_code
                code_result = run_python_code(code_text, input_data=current_input)
                if code_result.get("success"):
                    output_text = code_result.get("output", "")
                    result_val = code_result.get("result")
                    display = output_text
                    if result_val is not None:
                        display = (display + "\nresult = " + str(result_val)).strip()
                    log(node_id, "success", f"代码执行成功", display or "(无输出)")
                    # 优先用 result 变量的值作为下游输入，其次用 print 输出
                    if result_val is not None:
                        current_input = str(result_val)
                    else:
                        current_input = output_text
                else:
                    err_msg = code_result.get("error", "未知错误")
                    out_msg = code_result.get("output", "")
                    full_msg = (out_msg + "\n" + err_msg).strip()
                    log(node_id, "error", f"代码执行失败: {err_msg}", full_msg)
            except Exception as err:
                log(node_id, "error", f"沙箱调用失败: {str(err)}", current_input)

        elif node.type == "template":
            data = node.data or {}
            scene = data.get("scene", "")
            scene_map = {"chat": "日常闲聊", "office": "办公文案", "study": "学习答疑", "life": "生活解惑"}
            scene_name = scene_map.get(scene, "通用模式")
            log(node_id, "success", f"已应用场景：{scene_name}", current_input)

        elif node.type == "condition":
            data = node.data or {}
            expr = (data.get("expression", "") or "").strip()
            cond_result = False
            try:
                safe_dict = {"input": current_input, "len": len, "True": True, "False": False}
                if expr:
                    cond_result = bool(eval(expr, {"__builtins__": {}}, safe_dict))
                else:
                    cond_result = bool(current_input)
            except Exception:
                cond_result = False
            log(node_id, "success", f"条件结果：{'满足' if cond_result else '不满足'}", current_input)
            if len(out_edges) >= 2:
                target = out_edges[0].target if cond_result else out_edges[1].target
                if target not in executed:
                    queue.append(target)
                executed.add(node_id)
                continue

        elif node.type == "loop":
            data = node.data or {}
            mode = data.get("mode", "count")  # count / list
            # 判断是否首次执行
            if node_id not in executed:
                # 首次执行：准备迭代数据
                if mode == "list":
                    list_raw = data.get("list", "") or ""
                    items = [x.strip() for x in list_raw.split(",") if x.strip()]
                    if not items:
                        items = [current_input]
                else:  # count
                    cnt = int(data.get("count", 1) or 1)
                    items = [current_input] * max(1, cnt)

                # 保存循环状态到 node_outputs（用特殊结构）
                loop_state = {"items": items, "index": 0, "results": []}
                node_outputs[node_id + "__loop_state"] = loop_state
                log(node_id, "running", f"开始循环（共 {len(items)} 次）")
                executed.add(node_id)

                # 执行第一次迭代
                first_item = items[0]
                log(node_id + f"#iter_0", "success", f"第 1 次迭代输入", first_item)
                _enqueue_downstream(node_id, queue, extra_input=first_item)
                continue
            else:
                # 继续循环：获取循环状态
                loop_state = node_outputs.get(node_id + "__loop_state")
                if not loop_state:
                    executed.add(node_id)
                    continue
                items = loop_state["items"]
                idx = loop_state["index"]

                # 保存这次迭代的结果（上游输出）
                if current_input:
                    loop_state["results"].append(current_input)

                idx += 1
                if idx < len(items):
                    # 继续下一次迭代
                    loop_state["index"] = idx
                    next_item = items[idx]
                    log(node_id + f"#iter_{idx}", "success", f"第 {idx + 1} 次迭代输入", next_item)
                    _enqueue_downstream(node_id, queue, extra_input=next_item)
                    continue
                else:
                    # 循环结束，合并结果
                    results = loop_state["results"]
                    final = "\n\n---\n\n".join([str(r) for r in results if r is not None])
                    log(node_id, "success", f"循环完成（{len(results)} 次）", final)
                    current_input = final

        elif node.type == "user_input":
            data = node.data or {}
            ph = data.get("placeholder", "请输入...")
            log(node_id, "waiting", f"等待用户输入：{ph}", current_input)
            executed.add(node_id)
            return {
                "code": 202,
                "msg": "需要用户输入",
                "waiting_node_id": node_id,
                "execution_log": execution_log,
                "node_outputs": node_outputs,
            }

        executed.add(node_id)
        _enqueue_downstream(node_id, queue)

    # 返回执行结果
    final_output = None
    if end_nodes:
        final_output = node_outputs.get(end_nodes[0].id, current_input if 'current_input' in dir() else "")
    else:
        final_output = current_input if 'current_input' in dir() else ""

    return {
        "code": 200,
        "msg": "执行完成",
        "execution_log": execution_log,
        "node_outputs": node_outputs,
        "final_output": final_output,
    }


# ==================== 找工作：简历 + 岗位推荐 ====================

class JobProfilePayload(BaseModel):
    name: str = ""
    gender: str = ""
    age: str = ""
    education: str = ""
    major: str = ""
    school: str = ""
    experience_years: str = ""
    target_city: str = ""
    target_role: str = ""
    skills: str = ""
    work_experience: str = ""
    project_experience: str = ""
    self_intro: str = ""
    preset_resume: str = ""


class JobProfileSaveRequest(BaseModel):
    profile: JobProfilePayload
    template_id: str = "classic"
    resume_content: Optional[str] = None


class JobGenerateResumeRequest(BaseModel):
    profile: JobProfilePayload
    template_id: str = "classic"
    lang: str = "zh"


class JobMatchRequest(BaseModel):
    profile: JobProfilePayload
    resume_content: str = ""


@app.get("/ai/job/templates", summary="简历模板列表")
def job_templates():
    return {"code": 200, "templates": RESUME_TEMPLATES}


@app.get("/ai/job/mock-jobs", summary="虚拟岗位列表（BOSS直聘风格）")
def job_mock_list():
    return {"code": 200, "jobs": MOCK_JOBS, "source": "mock"}


@app.get("/ai/job/profile", summary="获取用户求职画像")
def get_job_profile(
        db: Session = Depends(get_db),
        user_id: int = Depends(verify_token),
):
    record = db.query(JobProfile).filter(JobProfile.user_id == user_id).first()
    if not record:
        return {"code": 200, "profile": {}, "template_id": "classic", "resume_content": ""}
    return {
        "code": 200,
        "profile": record.profile_data or {},
        "template_id": record.template_id or "classic",
        "resume_content": record.resume_content or "",
    }


@app.post("/ai/job/profile", summary="保存用户求职画像")
def save_job_profile(
        request: JobProfileSaveRequest,
        db: Session = Depends(get_db),
        user_id: int = Depends(verify_token),
):
    record = db.query(JobProfile).filter(JobProfile.user_id == user_id).first()
    profile_dict = request.profile.model_dump()
    if record:
        record.profile_data = profile_dict
        record.template_id = request.template_id
        if request.resume_content is not None:
            record.resume_content = request.resume_content
    else:
        record = JobProfile(
            user_id=user_id,
            profile_data=profile_dict,
            template_id=request.template_id,
            resume_content=request.resume_content or "",
        )
        db.add(record)
    db.commit()
    return {"code": 200, "msg": "画像已保存"}


@app.post("/ai/job/generate-resume", summary="AI 完善简历")
def generate_job_resume(
        request: JobGenerateResumeRequest,
        http_request: Request,
        db: Session = Depends(get_db),
        user_id: Optional[int] = Depends(get_optional_user_id),
):
    ensure_chat_access(http_request, user_id)

    template_name = next(
        (t["name"] for t in RESUME_TEMPLATES if t["id"] == request.template_id),
        "经典简约",
    )
    profile = request.profile.model_dump()
    preset = profile.get("preset_resume") or ""

    if (request.lang or "zh").lower().startswith("en"):
        prompt = f"""You are a professional resume consultant. Based on the profile and draft below, produce a complete, professional, ready-to-submit English resume in the "{template_name}" style.

Requirements:
1. Use Markdown format with a clear structure (Basic Info, Objective, Education, Work/Project Experience, Skills, Summary)
2. Polish, complete and quantify achievements based on the draft; do not fabricate experience that clearly contradicts the profile
3. Keep the language concise and professional, suitable for job platforms
4. Output only the resume body, no extra explanation

[Profile]
{json.dumps(profile, ensure_ascii=False, indent=2)}

[Resume Draft]
{preset or "(No draft, please generate from the profile)"}
"""
    else:
        prompt = f"""你是一名专业简历顾问。请根据以下个人画像和预设简历草稿，按「{template_name}」风格输出一份完整、专业、可直接投递的中文简历。

要求：
1. 使用 Markdown 格式，结构清晰（基本信息、求职意向、教育背景、工作/项目经历、技能、自我评价）
2. 在草稿基础上润色、补全、量化成果，不要编造与画像明显矛盾的经历
3. 语言简洁专业，适合 BOSS 直聘等平台
4. 只输出简历正文，不要额外解释

【个人画像】
{json.dumps(profile, ensure_ascii=False, indent=2)}

【预设简历草稿】
{preset or "（无草稿，请根据画像生成）"}
"""

    model = init_chat_model(
        model=MODEL,
        model_provider="openai",
        base_url=DASHSCOPE_URL,
        api_key=DASHSCOPE_API_KEY,
        temperature=0.7,
    )
    result = model.invoke([HumanMessage(content=prompt)])
    resume_text = result.content if hasattr(result, "content") else str(result)

    if user_id:
        record = db.query(JobProfile).filter(JobProfile.user_id == user_id).first()
        if record:
            record.resume_content = resume_text
            record.profile_data = profile
            record.template_id = request.template_id
        else:
            db.add(JobProfile(
                user_id=user_id,
                profile_data=profile,
                template_id=request.template_id,
                resume_content=resume_text,
            ))
        db.commit()

    return {"code": 200, "resume": resume_text}


@app.post("/ai/job/match", summary="匹配推荐岗位")
def match_job_recommendations(
        request: JobMatchRequest,
        http_request: Request,
        user_id: Optional[int] = Depends(get_optional_user_id),
):
    ensure_chat_access(http_request, user_id)
    profile = request.profile.model_dump()
    jobs = match_jobs(profile, request.resume_content)
    return {"code": 200, "jobs": jobs, "source": "mock"}


# ===================== 简历漏洞检测 =====================

class ResumeAuditRequest(BaseModel):
    profile: JobProfilePayload
    resume_content: str = ""


@app.post("/ai/job/resume-audit", summary="AI 简历漏洞检测")
def resume_audit(
        request: ResumeAuditRequest,
        http_request: Request,
        user_id: Optional[int] = Depends(get_optional_user_id),
):
    """对简历进行多维度漏洞检测，返回问题列表和优化建议。"""
    ensure_chat_access(http_request, user_id)
    profile = request.profile.model_dump()
    resume = request.resume_content or profile.get("preset_resume") or ""

    lang = (profile.get("lang") or "zh").lower()
    if lang.startswith("en"):
        prompt = f"""You are a senior HR and resume consultant. Conduct a thorough audit of the resume below and identify ALL potential issues across these dimensions:

1. **Content Completeness** - Missing sections, sparse information, lack of quantifiable results
2. **Format & Structure** - Poor organization, inconsistent formatting, length issues
3. **Keyword Optimization** - Missing industry keywords, ATS-unfriendly language
4. **Professional Tone** - Casual language, vague statements, clichés
5. **Experience Presentation** - Poor action verbs, lack of STAR method, no metrics
6. **Red Flags** - Employment gaps unexplained, job-hopping patterns, irrelevant content

For each issue found, provide:
- **category**: one of the 6 dimensions above
- **severity**: "high" / "medium" / "low"
- **issue**: specific description of the problem
- **suggestion**: concrete, actionable fix

Also provide an overall **score** (0-100) and an **overall_summary** (2-3 sentences).

Return ONLY a JSON object in this exact format:
{{
    "score": 75,
    "overall_summary": "...",
    "issues": [
        {{"category": "...", "severity": "...", "issue": "...", "suggestion": "..."}}
    ]
}}

[Profile]
{json.dumps(profile, ensure_ascii=False, indent=2)}

[Resume]
{resume or "(No resume provided - audit based on profile only)"}
"""
    else:
        prompt = f"""你是一位资深 HR 和简历顾问。请对以下简历进行全面漏洞检测，从以下 6 个维度找出所有潜在问题：

1. **内容完整性** - 模块缺失、信息量不足、缺乏量化成果
2. **格式与结构** - 排版混乱、格式不统一、篇幅不合理
3. **关键词优化** - 缺少行业关键词、表述不利于 ATS 系统识别
4. **专业语气** - 口语化严重、表述模糊、套话空话
5. **经历呈现** - 缺乏行动动词、未用 STAR 法则、无数据支撑
6. **风险信号** - 空窗期未说明、跳槽频繁、无关信息过多

对每个问题，请提供：
- **category**：所属维度（6 个之一）
- **severity**：严重程度 "high" / "medium" / "low"
- **issue**：具体问题描述
- **suggestion**：可落地的修改建议

最后给出整体 **score**（0-100 分）和 **overall_summary**（2-3 句话）。

请只返回 JSON，格式如下：
{{
    "score": 75,
    "overall_summary": "...",
    "issues": [
        {{"category": "...", "severity": "...", "issue": "...", "suggestion": "..."}}
    ]
}}

【个人画像】
{json.dumps(profile, ensure_ascii=False, indent=2)}

【简历内容】
{resume or "（无简历内容 - 仅根据画像检测）"}
"""

    model = init_chat_model(
        model=MODEL,
        model_provider="openai",
        base_url=DASHSCOPE_URL,
        api_key=DASHSCOPE_API_KEY,
        temperature=0.5,
    )
    result = model.invoke([HumanMessage(content=prompt)])
    raw = result.content if hasattr(result, "content") else str(result)

    # 尝试解析 JSON
    try:
        # 清理可能的 markdown 代码块标记
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        audit_data = json.loads(cleaned)
    except (json.JSONDecodeError, Exception) as e:
        # 兜底：返回基础检测结果
        audit_data = {
            "score": 60,
            "overall_summary": "简历解析完成，建议补充更多细节和量化成果。" if not lang.startswith("en") else "Resume parsed, suggest adding more details and quantifiable achievements.",
            "issues": [
                {"category": "内容完整性", "severity": "medium",
                 "issue": "简历细节不足" if not lang.startswith("en") else "Insufficient resume details",
                 "suggestion": "请补充工作经历中的具体项目、成果数据和技术细节" if not lang.startswith("en") else "Please add specific projects, metrics and technical details in work experience"}
            ]
        }

    return {"code": 200, "audit": audit_data}


# ===================== 模拟面试 =====================

class MockInterviewRequest(BaseModel):
    profile: JobProfilePayload
    resume_content: str = ""
    round: int = 1  # 第几个问题（1=开场自我介绍，2+=技术/行为问题）
    last_answer: str = ""  # 上一轮用户的回答
    interview_type: str = "general"  # general / technical / behavioral


@app.post("/ai/job/mock-interview", summary="AI 模拟面试")
def mock_interview(
        request: MockInterviewRequest,
        http_request: Request,
        user_id: Optional[int] = Depends(get_optional_user_id),
):
    """模拟面试：根据画像和简历，逐轮生成面试问题并对回答进行点评。"""
    ensure_chat_access(http_request, user_id)
    profile = request.profile.model_dump()
    resume = request.resume_content or profile.get("preset_resume") or ""
    target_role = profile.get("target_role") or profile.get("skills") or "软件开发"
    interview_round = request.round
    last_answer = request.last_answer or ""
    itype = request.interview_type

    lang = (profile.get("lang") or "zh").lower()
    is_en = lang.startswith("en")

    if interview_round == 1:
        # 第一轮：开场 + 自我介绍要求
        if is_en:
            prompt = f"""You are a professional interviewer for the position of "{target_role}".

This is Round 1 - Opening. Please:
1. Greet the candidate warmly
2. Briefly introduce yourself as the interviewer
3. Ask them to start with a self-introduction (1-2 minutes)

Consider the candidate's profile:
{json.dumps(profile, ensure_ascii=False, indent=2)}

Return ONLY a JSON object:
{{
    "question": "...",
    "round": 1,
    "interviewer_intro": "...",
    "tips": "1-2 minutes, focus on highlights relevant to the role"
}}
"""
        else:
            prompt = f"""你是一名「{target_role}」岗位的专业面试官。

当前是第 1 轮 - 开场。请：
1. 友好地问候候选人
2. 简单介绍自己（面试官身份）
3. 请候选人做一个 1-2 分钟的自我介绍

候选人画像参考：
{json.dumps(profile, ensure_ascii=False, indent=2)}

请只返回 JSON：
{{
    "question": "...",
    "round": 1,
    "interviewer_intro": "...",
    "tips": "1-2分钟，重点突出与岗位相关的亮点"
}}
"""
    else:
        # 后续轮次：点评上一轮回答 + 提出新问题
        if is_en:
            prompt = f"""You are a professional interviewer for "{target_role}".

Previous context:
- Candidate Profile: {json.dumps(profile, ensure_ascii=False, indent=2)}
- Resume: {resume[:1000]}
- Interview Round: {interview_round}
- Interview Type: {itype}
- Candidate's Last Answer: {last_answer[:2000]}

Please:
1. **Evaluate** the last answer on these criteria (score each 0-10):
   - Relevance to the question
   - Clarity and structure
   - Use of specific examples/data
   - Professional communication

2. **Provide feedback** (1-2 sentences): What was good, what to improve.

3. **Ask the NEXT question** appropriate for round {interview_round}:
   - Round 2-3: Technical questions related to {target_role} skills
   - Round 4-5: Behavioral/STAR questions (conflict, leadership, failure, achievement)
   - Round 6+: Domain-specific deep dive or case questions

Return ONLY a JSON object:
{{
    "feedback": {{"relevance": 8, "clarity": 7, "examples": 6, "communication": 8, "comment": "..."}},
    "question": "...",
    "round": {interview_round},
    "question_type": "technical/behavioral/case",
    "tips": "..."
}}
"""
        else:
            prompt = f"""你是一名「{target_role}」岗位的专业面试官。

背景信息：
- 候选人画像：{json.dumps(profile, ensure_ascii=False, indent=2)}
- 简历：{resume[:1000]}
- 当前轮次：第 {interview_round} 轮
- 面试类型：{itype}
- 候选人上一轮回答：{last_answer[:2000]}

请完成：
1. **点评上一轮回答**，从以下维度评分（每项 0-10 分）：
   - 切题程度
   - 清晰度与条理性
   - 实例/数据支撑
   - 表达专业性

2. **给出反馈**（1-2 句话）：回答好在哪里，哪些地方可以改进。

3. **提出下一个问题**，适合第 {interview_round} 轮：
   - 第 2-3 轮：与「{target_role}」技能相关的技术问题
   - 第 4-5 轮：行为面试题（STAR 法则）—— 冲突处理、领导力、失败经历、成就感等
   - 第 6 轮以后：深度专业问题或案例分析题

请只返回 JSON：
{{
    "feedback": {{"relevance": 8, "clarity": 7, "examples": 6, "communication": 8, "comment": "..."}},
    "question": "...",
    "round": {interview_round},
    "question_type": "technical/behavioral/case",
    "tips": "..."
}}
"""

    model = init_chat_model(
        model=MODEL,
        model_provider="openai",
        base_url=DASHSCOPE_URL,
        api_key=DASHSCOPE_API_KEY,
        temperature=0.7,
    )
    result = model.invoke([HumanMessage(content=prompt)])
    raw = result.content if hasattr(result, "content") else str(result)

    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        interview_data = json.loads(cleaned)
    except (json.JSONDecodeError, Exception) as e:
        # 兜底
        if is_en:
            interview_data = {
                "question": "Thank you. Now let's move to the next question. Tell me about a challenging project you worked on.",
                "round": interview_round,
                "feedback": {"relevance": 7, "clarity": 7, "examples": 6, "communication": 7, "comment": "Good answer, could add more specific examples."},
                "question_type": "behavioral",
                "tips": "Use STAR method: Situation, Task, Action, Result",
            }
        else:
            interview_data = {
                "question": "谢谢分享。我们来看看下一个问题——请讲一个你做过的有挑战性的项目。",
                "round": interview_round,
                "feedback": {"relevance": 7, "clarity": 7, "examples": 6, "communication": 7, "comment": "回答不错，可以补充更多具体实例和数据。"},
                "question_type": "behavioral",
                "tips": "建议使用 STAR 法则：情境、任务、行动、结果",
            }

    return {"code": 200, "interview": interview_data}


# ==================== 推广拉新 / 钱包 ====================

class TrackDownloadRequest(BaseModel):
    ref: str = ""
    fingerprint: str = ""


class WithdrawSubmitRequest(BaseModel):
    paypal_email: str


@app.get("/ai/promo/config", summary="推广展示配置（公开）")
def promo_config(db: Session = Depends(get_db)):
    """返回前端展示所需的文案与开关，不含金额等敏感项。"""
    cfg = promo.get_config_map(db)
    return {
        "code": 200,
        "promo_enabled": promo._is_on(cfg.get("promo_enabled")),
        "input_promo_enabled": promo._is_on(cfg.get("input_promo_enabled")),
        "link_cache_days": promo._to_int(cfg.get("link_cache_days"), 30),
        "popup_intro": {"zh": cfg.get("popup_intro_zh", ""), "en": cfg.get("popup_intro_en", "")},
        "input_promo": {"zh": cfg.get("input_promo_zh", ""), "en": cfg.get("input_promo_en", "")},
        "banner_promo": {"zh": cfg.get("banner_promo_zh", ""), "en": cfg.get("banner_promo_en", "")},
    }


@app.get("/ai/promo/my-link", summary="获取我的专属推广链接")
def promo_my_link(
        db: Session = Depends(get_db),
        user_id: int = Depends(verify_token),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "用户不存在"})
    code = promo.get_or_create_referral_code(db, user)
    return {"code": 200, "referral_code": code, "link": promo.build_referral_link(db, code)}


@app.post("/ai/promo/track-download", summary="记录下载控件点击并给推广人发奖（公开）")
def promo_track_download(
        request: TrackDownloadRequest,
        http_request: Request,
        db: Session = Depends(get_db),
        user_id: Optional[int] = Depends(get_optional_user_id),
):
    ip = promo.client_ip(http_request)
    ref = (request.ref or "").strip()
    fingerprint = (request.fingerprint or "").strip()

    # 点击埋点（总点击量，可重复）——失败不影响发奖主流程
    try:
        promo.record_download_click(db, ip=ip, fingerprint=fingerprint, ref_code=ref)
    except Exception as e:
        logger.warning(f"[埋点] 下载点击记录失败：{e}")

    result = promo.track_download(
        db,
        ref_code=ref,
        fingerprint=fingerprint,
        ip=ip,
        visitor_user_id=user_id,
    )
    return {"code": 200, **result.to_dict()}


@app.get("/ai/promo/wallet", summary="我的钱包（余额 + 提现记录）")
def promo_wallet(
        db: Session = Depends(get_db),
        user_id: int = Depends(verify_token),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "用户不存在"})
    records = db.query(WithdrawRequest).filter(
        WithdrawRequest.user_id == user_id
    ).order_by(WithdrawRequest.created_at.desc()).all()
    return {
        "code": 200,
        "balance": round(user.balance_usd or 0.0, 2),
        "referral_count": user.referral_count or 0,
        "records": [
            {
                "id": r.id,
                "amount": round(r.amount, 2),
                "paypal_email": r.paypal_email,
                "status": r.status,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
            }
            for r in records
        ],
    }


@app.get("/ai/promo/checkin-status", summary="获取我的签到状态")
def promo_checkin_status(
        db: Session = Depends(get_db),
        user_id: int = Depends(verify_token),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "用户不存在"})
    return {"code": 200, **promo.get_checkin_status(db, user)}


@app.post("/ai/promo/checkin", summary="签到领奖励")
def promo_checkin(
        db: Session = Depends(get_db),
        user_id: int = Depends(verify_token),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "用户不存在"})
    result = promo.do_checkin(db, user)
    if not result.ok:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "签到功能已关闭"})
    return {"code": 200, **result.to_dict()}


@app.get("/ai/promo/withdraw-available", summary="查询可提现金额（含风控校验）")
def promo_withdraw_available(
        db: Session = Depends(get_db),
        user_id: int = Depends(verify_token),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "用户不存在"})
    return {"code": 200, **promo.get_withdraw_available(db, user)}


@app.post("/ai/promo/withdraw", summary="提交提现申请（提现全部余额）")
def promo_withdraw(
        request: WithdrawSubmitRequest,
        db: Session = Depends(get_db),
        user_id: int = Depends(verify_token),
):
    email = (request.paypal_email or "").strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "请输入有效的 PayPal 邮箱"})

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "用户不存在"})

    # ===== 提现风控校验 =====
    withdraw_info = promo.get_withdraw_available(db, user)
    if not withdraw_info["can_withdraw"]:
        reasons = "；".join(withdraw_info["reasons"]) or "暂不可提现"
        raise HTTPException(status_code=400, detail={"code": 400, "msg": reasons})

    balance = withdraw_info["balance"]
    if balance <= 0:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "余额不足，无法提现"})

    # 提现全部余额：建 pending 申请并从余额扣除转入待审核
    # 后台驳回时会自动把 amount 退回 balance（见 /admin/api/withdraws/{id}/reject）
    record = WithdrawRequest(user_id=user_id, amount=balance, paypal_email=email, status="pending")
    db.add(record)
    user.balance_usd = 0.0
    db.commit()
    return {"code": 200, "msg": "提现申请已提交，等待人工审核", "amount": balance}


# ==================== 后台管理 /admin ====================

class AdminLoginForm(BaseModel):
    username: str
    password: str


class AdminConfigUpdate(BaseModel):
    items: dict  # {key: value, ...}


class AdminBalanceAdjust(BaseModel):
    amount: float          # 正数加钱，负数扣钱
    reason: str = ""


@app.get("/admin", summary="后台管理页", description="返回后台单页，数据靠 /admin/api/* 异步拉取")
def admin_page(request: Request):
    return templates.TemplateResponse(name="admin.html", request=request)


@app.post("/admin/api/login", summary="后台登录")
def admin_login(form: AdminLoginForm):
    # 密码留空则一律拒绝，避免默认空密码被登入
    if not config.ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail={"code": 403, "msg": "后台未设置管理员密码，请在 .env 配置 ADMIN_PASSWORD"})
    if form.username == config.ADMIN_USERNAME and form.password == config.ADMIN_PASSWORD:
        return {"code": 200, "token": create_admin_token()}
    raise HTTPException(status_code=401, detail={"code": 401, "msg": "账号或密码错误"})


@app.get("/admin/api/stats", summary="后台数据看板")
def admin_stats(db: Session = Depends(get_db), _: bool = Depends(verify_admin_token)):
    return {"code": 200, **promo.get_admin_stats(db)}


@app.get("/admin/api/users", summary="用户列表")
def admin_users(
        q: str = Query("", description="按用户名搜索"),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        db: Session = Depends(get_db),
        _: bool = Depends(verify_admin_token),
):
    query = db.query(User)
    if q.strip():
        query = query.filter(User.username.like(f"%{q.strip()}%"))
    total = query.count()
    rows = query.order_by(User.id.desc()).offset(offset).limit(limit).all()
    return {
        "code": 200,
        "total": total,
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "balance": round(u.balance_usd or 0.0, 2),
                "referral_count": u.referral_count or 0,
                "referral_code": u.referral_code or "",
                "membership_expire_at": u.membership_expire_at.strftime("%Y-%m-%d") if u.membership_expire_at else "",
                "register_time": u.register_time.strftime("%Y-%m-%d %H:%M") if u.register_time else "",
            }
            for u in rows
        ],
    }


@app.post("/admin/api/users/{uid}/balance", summary="手动调整用户余额")
def admin_adjust_balance(
        uid: int,
        body: AdminBalanceAdjust,
        db: Session = Depends(get_db),
        _: bool = Depends(verify_admin_token),
):
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "用户不存在"})
    new_balance = round((user.balance_usd or 0.0) + body.amount, 2)
    if new_balance < 0:
        raise HTTPException(status_code=400, detail={"code": 400, "msg": "调整后余额不能为负"})
    user.balance_usd = new_balance
    db.commit()
    return {"code": 200, "msg": "已调整", "balance": new_balance}


@app.get("/admin/api/withdraws", summary="提现申请列表")
def admin_withdraws(
        status_filter: str = Query("", alias="status", description="pending/paid/rejected，空=全部"),
        db: Session = Depends(get_db),
        _: bool = Depends(verify_admin_token),
):
    query = db.query(WithdrawRequest)
    if status_filter in ("pending", "paid", "rejected"):
        query = query.filter(WithdrawRequest.status == status_filter)
    rows = query.order_by(WithdrawRequest.created_at.desc()).all()
    # 附带用户名
    user_map = {u.id: u.username for u in db.query(User).all()}
    return {
        "code": 200,
        "withdraws": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "username": user_map.get(r.user_id, f"#{r.user_id}"),
                "amount": round(r.amount, 2),
                "paypal_email": r.paypal_email,
                "status": r.status,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
                "reviewed_at": r.reviewed_at.strftime("%Y-%m-%d %H:%M") if r.reviewed_at else "",
            }
            for r in rows
        ],
    }


@app.post("/admin/api/withdraws/{wid}/approve", summary="通过提现")
def admin_withdraw_approve(
        wid: int,
        db: Session = Depends(get_db),
        _: bool = Depends(verify_admin_token),
):
    record = db.query(WithdrawRequest).filter(WithdrawRequest.id == wid).first()
    if not record:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "提现记录不存在"})
    if record.status != "pending":
        raise HTTPException(status_code=400, detail={"code": 400, "msg": f"该申请已是 {record.status}，无法重复处理"})
    record.status = "paid"
    record.reviewed_at = datetime.now()
    db.commit()
    return {"code": 200, "msg": "已标记为已打款"}


@app.post("/admin/api/withdraws/{wid}/reject", summary="驳回提现（余额退回用户）")
def admin_withdraw_reject(
        wid: int,
        db: Session = Depends(get_db),
        _: bool = Depends(verify_admin_token),
):
    record = db.query(WithdrawRequest).filter(WithdrawRequest.id == wid).first()
    if not record:
        raise HTTPException(status_code=404, detail={"code": 404, "msg": "提现记录不存在"})
    if record.status != "pending":
        raise HTTPException(status_code=400, detail={"code": 400, "msg": f"该申请已是 {record.status}，无法重复处理"})
    record.status = "rejected"
    record.reviewed_at = datetime.now()
    # 把冻结的金额退回用户余额
    user = db.query(User).filter(User.id == record.user_id).first()
    if user:
        user.balance_usd = round((user.balance_usd or 0.0) + record.amount, 2)
    db.commit()
    return {"code": 200, "msg": "已驳回，金额已退回用户余额"}


@app.get("/admin/api/config", summary="获取全部推广配置")
def admin_get_config(db: Session = Depends(get_db), _: bool = Depends(verify_admin_token)):
    return {"code": 200, "config": promo.get_config_map(db)}


@app.post("/admin/api/config", summary="批量更新推广配置")
def admin_set_config(
        body: AdminConfigUpdate,
        db: Session = Depends(get_db),
        _: bool = Depends(verify_admin_token),
):
    allowed = set(PROMO_CONFIG_DEFAULTS.keys())
    updated = []
    for key, value in body.items.items():
        if key not in allowed:
            continue  # 只允许改已知配置项，忽略未知 key
        row = db.query(PromoConfig).filter(PromoConfig.key == key).first()
        if row:
            row.value = str(value)
        else:
            db.add(PromoConfig(key=key, value=str(value)))
        updated.append(key)
    db.commit()
    return {"code": 200, "msg": "已保存", "updated": updated}


# ------------------- 接口：登录 ------------------
class LoginForm(BaseModel):
    username: str
    password: str


@app.post('/login', summary='登录')
def login(
        form: LoginForm,
        db: Session = Depends(get_db),

):
    existing_user = db.query(User).filter(
        User.username == form.username,
    ).first()
    if existing_user and verify_password(form.password, existing_user.password):
        if needs_rehash(existing_user.password):
            existing_user.password = hash_password(form.password)
            db.commit()
        token: str = create_access_token({'user_id': existing_user.id})
        return {
            "code": 200,
            "msg": "登录成功",
            "token": token,
            "user_id": existing_user.id,
        }
    else:
        return {
            "code": 401,
            "msg": "用户名或密码错误"
        }


class RegisterForm(BaseModel):
    username: str
    password: str


@app.post('/register', summary='注册')
def register(
        form: RegisterForm,
        db: Session = Depends(get_db)
):
    existed_user = db.query(User).filter(
        User.username == form.username,
    ).first()
    if existed_user:
        return {'code': 401, "msg": "已存在用户名"}
    else:
        new_user = User(
            username=form.username,
            password=hash_password(form.password),
        )
        db.add(new_user)
        db.commit()  # <-- 关键！提交后才有ID
        db.refresh(new_user)  # <-- 刷新对象，加载数据库生成的ID
        return {
            "code": 200,
            "msg": "注册成功",
        }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=1)
    # uvicorn main:app --host 0.0.0.0 --port 8000 --reload
