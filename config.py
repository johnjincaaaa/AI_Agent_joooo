# ===================== token.py =====================
# 密钥，自己改复杂点
SECRET_KEY = "my-super-secret-key-123456"
# 加密算法
ALGORITHM = "HS256"
# token 过期时间（分钟）
ACCESS_TOKEN_EXPIRE_MINUTES = 30


# ===================== main.py =====================
MODEL = 'ollama:llama3-groq-tool-use:8b'
SYSTEM_PROMPT = "你是一个乐于助人的助手，全程中文回答"
# 本地 Ollama 地址
OLLAMA_URL = "http://localhost:11434/api/chat"