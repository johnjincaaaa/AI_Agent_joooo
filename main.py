import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

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

# 允许跨域（让你的 HTML 页面可以调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 定义消息结构
class ChatMessage(BaseModel):
    role: str       # user / assistant
    message: str

# 前端传过来的结构
class ChatRequest(BaseModel):
    history: List[ChatMessage]  # 完整历史
    newMessage: str             # 最新一条消息
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
    full_history.append(ChatMessage(role='user',message=request.newMessage))
    # ==========================================
    # 2. 【关键】只取最后 20 条给 AI
    # ==========================================
    ai_context = full_history[-20:]  # 取最后20条！

    # ==========================================
    # 3. 把 ai_context 传给 AI
    # ==========================================
    model = init_chat_model(model="ollama:llama3-groq-tool-use:8b", temperature=0,num_gpu=-1)
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



# # ------------------- 你可以加各种工具接口 -------------------
# @app.get("/tool/weather")
# def get_weather(city: str):
#     # 这里你可以写查天气、查时间、操作文件、控制硬件...
#     return {"city": city, "weather": "晴天", "temp": "25℃"}
#
# @app.get("/tool/time")
# def get_time():
#     from datetime import datetime
#     return {"now": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000,workers=1)