# ===================== token.py =====================
# 密钥，自己改复杂点
SECRET_KEY = "my-super-secret-key-123456"
# 加密算法
ALGORITHM = "HS256"
# token 过期时间（分钟）
ACCESS_TOKEN_EXPIRE_MINUTES = 60


# ===================== main.py =====================
# MODEL = 'ollama:llama3-groq-tool-use:8b'

SYSTEM_PROMPT = "你是一个乐于助人的助手，全程中文回答"
# 本地 Ollama 地址
OLLAMA_URL = "http://localhost:11434/api/chat"

# 阿里云配置
MODEL = "qwen3.7-plus"
DASHSCOPE_API_KEY = "sk-910580700c1a44d2944152fda72177b4"
# 阿里云兼容openai接口地址
DASHSCOPE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# ===================== tools =====================
import tools
TOOL_LIST = []

# ===================== 数据库 =====================
SQLALCHEMY_DATABASE_URL =  "mysql+pymysql://root:147258@localhost:3306/ai_youliao"