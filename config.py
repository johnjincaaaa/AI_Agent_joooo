import os

from dotenv import load_dotenv

load_dotenv()

# ===================== JWT =====================
SECRET_KEY = os.getenv("SECRET_KEY", "")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# ===================== AI =====================
SYSTEM_PROMPT = "你是一个乐于助人的助手，全程中文回答"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL = os.getenv("MODEL", "qwen3.7-plus")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_URL = os.getenv("DASHSCOPE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

# ===================== 未登录限流 =====================
ANONYMOUS_RATE_LIMIT_MAX = int(os.getenv("ANONYMOUS_RATE_LIMIT_MAX", "10"))
ANONYMOUS_RATE_LIMIT_WINDOW = int(os.getenv("ANONYMOUS_RATE_LIMIT_WINDOW", "3600"))

# ===================== tools =====================
TOOL_LIST = []

# ===================== 数据库 =====================
SQLALCHEMY_DATABASE_URL = os.getenv(
    "SQLALCHEMY_DATABASE_URL",
    "mysql+pymysql://root:password@localhost:3306/ai_youliao",
)
