"""
应用常量（不随部署变化的固定值）——从 config.py 拆出。

- 文件上传白名单 + 大小上限
- TOOL_LIST（聊天侧工具注册表，运行时由 chat_routes 组装）
"""
from app.core.paths import uploads_dir

# ==================================================================
# File upload (chat attachments)
# ==================================================================
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
MAX_IMAGE_SIZE = 10 * 1024 * 1024   # 10MB
MAX_DOCUMENT_SIZE = 20 * 1024 * 1024  # 20MB
UPLOAD_DIR = uploads_dir()

# ==================================================================
# Tool list（聊天场景用，由 chat_routes.build_tool_list 消费）
# ==================================================================
TOOL_LIST: list = []
