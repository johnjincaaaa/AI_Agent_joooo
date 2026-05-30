from sqlalchemy.orm import Session
import uvicorn
from fastapi import FastAPI, Request, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
from config import *
from token_utils import create_access_token, verify_token

try:
    from langchain.chat_models import init_chat_model
    from langchain.agents import create_agent
    from langchain.messages import HumanMessage
    from langchain.messages import SystemMessage
    from langchain.messages import AIMessage
    from langchain.messages import ToolMessage
except ModuleNotFoundError as e:
    print(e)

# 初始化 FastAPI 应用
app = FastAPI(
    title="有料ai",
    description="一个致力于取悦自我的ai应用",
    version="1.0",

)
app.mount("/static", StaticFiles(directory="static"), name="static")  # ✅ 静态文件统一配置（全局只需这一句）
templates = Jinja2Templates(directory="templates")  # 自动找 HTML

# 允许跨域（让你的 HTML 页面可以调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 登录页
# @app.get("/")
# def login_page(request: Request):
#     return templates.TemplateResponse("login.html", {"request": request})
#
# # 注册页
# @app.get("/register")
# def register_page(request: Request):
#     return templates.TemplateResponse("register.html", {"request": request})

# ------------------- 聊天页 -------------------
@app.get("/chat", summary="聊天页",
         description="启动入口，返回html")
def chat_page(request: Request):
    return templates.TemplateResponse(name="ai.html", request=request)


# 定义消息结构
class ChatMessage(BaseModel):
    role: str  # user / assistant
    message: str


# 前端传过来的结构
class ChatRequest(BaseModel):
    history: List[ChatMessage]  # 完整历史
    newMessage: str  # 最新一条消息


"""
{
  "history": [
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好！"},
    ...
  ],
  "newMessage": "我最新说的话"
}
"""


# ------------------- 主接口：AI 聊天 -------------------
@app.post("/ai/chat", summary='AI 聊天'
    , description="""构建完整对话历史,取最后20条传给 AI，返回完整新历史给前端，前端同步内存""")
def ai_chat(
        request: ChatRequest,
        temperature:float = 0.7
):
    # ==========================================
    # 1. 构建完整对话历史 = 历史对话 + 最新发送
    # ==========================================
    full_history = request.history.copy()
    full_history.append(ChatMessage(role='user', message=request.newMessage))
    # ==========================================
    # 2. 【关键】只取最后 20 条给 AI
    # ==========================================
    ai_context = full_history[-20:]  # 取最后20条！

    # ==========================================
    # 3. 把 ai_context 传给 AI
    # ==========================================
    model = init_chat_model(model=MODEL, temperature=temperature, num_gpu=-1)
    # TODO:添加工具做成skill
    agent = create_agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
    )

    # 把最后20条转成 AI 能识别的格式
    messages = []
    for msg in ai_context:
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.message))
        else:
            messages.append(AIMessage(content=msg.message))
    try:
        result = agent.invoke({"messages": messages})
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
        User.password == form.password
    ).first()
    if existing_user:
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
            password=form.password,
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
