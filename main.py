from sqlalchemy.orm import Session
import uvicorn
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
from datetime import datetime

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
app = FastAPI()
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
@app.get("/chat")
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

# 本地 Ollama 地址
OLLAMA_URL = "http://localhost:11434/api/chat"


# ------------------- 主接口：AI 聊天 -------------------
@app.post("/ai/chat")
def ai_chat(request: ChatRequest):
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
    model = init_chat_model(model="ollama:llama3-groq-tool-use:8b", temperature=0, num_gpu=-1)
    # TODO:添加工具做成skill
    agent = create_agent(
        model=model,
        system_prompt="你是一个乐于助人的助手，全程中文回答",
    )

    # 把最后20条转成 AI 能识别的格式
    messages = []
    for msg in ai_context:
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.message))
        else:
            messages.append(AIMessage(content=msg.message))

    result = agent.invoke({"messages": messages})
    ai_reply = result["messages"][-1].content

    # ==========================================
    # 4. 【保存数据库】保存【完整对话】
    # ==========================================
    # 完整新历史 = (旧历史 + 用户新消息) + AI回复
    final_history = full_history + [{"role": "ai", "message": ai_reply}]

    # 这里保存 final_history 到 DB（根据当前登录用户ID）
    # db.save_history(user_id, final_history)

    # ==========================================
    # 5. 返回完整新历史给前端，前端同步内存
    # ==========================================
    return {
        "code": 200,
        "content": ai_reply,
        "new_history": final_history  # 前端用这个覆盖 chatData
    }


class ChatDbRequest(BaseModel):
    chat_data: List[ChatMessage]
    create_time: int
    session_name: str


# ------------------- 接口：接收数据并存入数据库 -------------------
from sqlOrm import *
@app.post('/ai/chat/savaToDb')
def ai_savaToDb(
        request: ChatDbRequest,
        db: Session = Depends(get_db)):
    # TODO:后续转化为用户凭证
    user_id = 1
    clean_time = request.create_time

    # ========================
    # 按 【user_id + 秒级时间】 查询
    # ========================
    existing_session = db.query(ChatSession).filter(
        ChatSession.user_id == user_id,
        ChatSession.session_time == clean_time
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
                session_time=clean_time,
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


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=1)
