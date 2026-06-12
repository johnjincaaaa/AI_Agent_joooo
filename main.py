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
from token_utils import create_access_token, verify_token, get_optional_user_id
from password_utils import hash_password, verify_password, needs_rehash
from rate_limit import check_anonymous_rate_limit
import tools
from tools.skills_registry import get_skill_catalog, resolve_tools

try:
    from langchain.chat_models import init_chat_model
    from langchain.agents import create_agent
    from langchain.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
except ModuleNotFoundError as e:
    print(e)

# 初始化 FastAPI 应用
app = FastAPI(
    title="有料ai",
    description="一个致力于取悦自我的ai应用",
    version="1.0",

)
app.mount("/static", StaticFiles(directory="static"), name="static")  # ✅ 静态文件统一配置（全局只需这一句）
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
templates = Jinja2Templates(directory="templates")  # 自动找 HTML

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
@app.get("/chat", summary="聊天页",
         description="启动入口，返回html")
def chat_page(request: Request):
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


def build_tool_list(open_online: bool, enabled_skills: Optional[List[str]] = None):
    tool_list = list(config.TOOL_LIST)
    tool_list.extend(resolve_tools(enabled_skills or []))
    if open_online:
        tool_list.extend([tools.online, tools.online_intensive])
    return tool_list


@app.get("/ai/skills", summary="获取可用技能列表")
def list_skills():
    return {"code": 200, "skills": get_skill_catalog()}


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


def ensure_chat_access(http_request: Request, user_id: Optional[int]) -> None:
    if user_id is None:
        check_anonymous_rate_limit(http_request)


# ==================== 改造后的 流式+历史 接口 ====================
@app.post("/ai/chatStream")
async def chat_stream(
        chat_request: ChatRequest,
        http_request: Request,
        temperature: float = 0.7,
        user_id: Optional[int] = Depends(get_optional_user_id),
):
    """SSE流式输出 + 最终返回完整对话历史"""
    ensure_chat_access(http_request, user_id)

    # 1. 构建历史（和原来完全一样）
    full_history = chat_request.history.copy()
    full_history.append(ChatMessage(role='user', message=chat_request.newMessage))
    ai_context = full_history[-20:]

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

    agent = create_agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
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

    # 返回SSE流式响应
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
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
    # 2. 【关键】只取最后 20 条给 AI
    # ==========================================
    ai_context = full_history[-20:]  # 取最后20条！

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
    tool_list = build_tool_list(
        chat_request.open_online,
        resolve_enabled_skills(
            chat_request.enabled_skills,
            chat_request.image_paths,
            chat_request.document_paths,
        ),
    )
    agent = create_agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
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
