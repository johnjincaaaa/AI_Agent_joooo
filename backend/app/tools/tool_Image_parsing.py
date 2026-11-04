"""
图片解析工具：提取图片基础信息（PIL）+ 识别图片内容（多模态模型）。

内容识别按 provider 选择通道（都失败则降级为仅基础信息，不再抛异常打断 Agent）：
  1. 阿里云百炼 / 通义千问 VL（provider=dashscope）
  2. 智谱 GLM 视觉（provider=glm，模型如 glm-4.6v-flash）
  3. 本地 Ollama 视觉模型（provider=ollama，Ollama 在运行时）
  4. 纯 PIL 降级：只返回格式/尺寸/模式/主色调，内容识别标注「未启用」

为什么不用 dashscope SDK：旧版硬编码走 MultiModalConversation，会把 LLM_MODEL
（如 deepseek-chat）误当成通义模型名去请求 dashscope，且 key 回退到 DeepSeek 的 key，
再加上系统代理会把 dashscope 请求 RST 掉，三者叠加导致必现 ProxyError。改成
OpenAI 兼容 HTTP + 本地 Ollama 通道后，不再依赖 dashscope SDK 与代理。
"""
from langchain.tools import tool
from PIL import Image
import base64
import io
import json
import os
import urllib.request
import urllib.error

import app.config as config


# ============ 用户配置注入（.env 打底，用户数据库配置覆盖） ============
# chat_routes 在构建 Agent 前调用 set_user_image_vl_config()，把登录用户在系统设置里
# 保存的图片解析配置注入进来；工具执行时优先用用户配置，回退 .env。
# 模块级变量 + 单用户本地部署为主；并发请求下配置错位影响极小（仅影响图片识别模型选择）。
_user_image_vl_config = None


def set_user_image_vl_config(cfg: dict | None) -> None:
    """注入当前请求的用户图片解析配置 {provider, base_url, model, api_key}。"""
    global _user_image_vl_config
    _user_image_vl_config = cfg or None


def get_user_image_vl_config() -> dict | None:
    return _user_image_vl_config


def _resolve_vl_config() -> dict:
    """返回统一图片解析配置 {provider, base_url, model, api_key}，用户配置覆盖 .env。

    provider 推断规则：
      - 用户显式 provider（dashscope / glm / ollama）
      - 否则按 .env 推断：有 DASHSCOPE_API_KEY → dashscope，
        有 GLM_API_KEY → glm，有 IMAGE_VL_MODEL → ollama
    """
    cfg = _user_image_vl_config or {}
    provider = (cfg.get("provider") or "").strip().lower()
    model = (cfg.get("model") or "").strip()
    api_key = (cfg.get("api_key") or "").strip()
    base_url = (cfg.get("base_url") or "").strip()

    # .env 兜底
    env_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    env_glm_key = os.getenv("GLM_API_KEY", "").strip()
    env_model = os.getenv("IMAGE_VL_MODEL", "").strip()
    if not provider:
        if env_key:
            provider = "dashscope"
        elif env_glm_key:
            provider = "glm"
        elif env_model:
            provider = "ollama"
    if not model:
        if provider == "dashscope":
            model = env_model or "qwen-vl-plus"
        elif provider == "glm":
            model = env_model or "glm-4.6v-flash"
        else:
            model = env_model or ""
    if not api_key:
        api_key = env_glm_key if provider == "glm" else env_key
    if not base_url:
        if provider == "ollama":
            base_url = os.getenv("OLLAMA_VL_URL", "http://localhost:11434/api/chat").strip()
        elif provider == "dashscope":
            base_url = os.getenv(
                "DASHSCOPE_VL_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            ).strip()
        elif provider == "glm":
            base_url = os.getenv(
                "GLM_VL_URL",
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            ).strip()

    return {"provider": provider, "base_url": base_url, "model": model, "api_key": api_key}


# ============ 基础信息提取（纯 PIL，永远可用） ============

def _extract_basic_info(image_path: str) -> str:
    img = Image.open(image_path)
    width, height = img.size
    img_format = img.format
    mode = img.mode
    channels = len(mode)
    has_alpha = img.mode in ("RGBA", "LA")
    file_size = os.path.getsize(image_path) // 1024

    # 主色调：缩到 1x1 取平均色
    small_img = img.convert("RGB").resize((1, 1))
    r, g, b = small_img.getpixel((0, 0))
    color_hex = "#{:02x}{:02x}{:02x}".format(r, g, b)

    return (
        "===== 图片基础信息 =====\n"
        f"格式：{img_format} | 尺寸：{width}x{height}\n"
        f"模式：{mode}({channels}通道) | 透明：{'是' if has_alpha else '否'}\n"
        f"大小：{file_size}KB | 主色调：{color_hex} RGB({r},{g},{b})"
    )


# ============ 图片预处理（大图压缩，避免请求体超限 400） ============

MAX_VL_EDGE = 2048          # 视觉模型输入最长边，超过则等比缩放
MAX_VL_BYTES = 3 * 1024 * 1024  # 原图超过 3MB 也走压缩


def _prepare_image_b64(image_path: str) -> str:
    """读图并压缩到视觉模型合理尺寸，返回 JPEG base64 字符串。

    前端可能传 7008x4672 / 12MB 的大图，直接 base64 会让请求体超限（GLM 返回 400）。
    等比缩到最长边 2048、JPEG 质量 85，体积降到数百 KB，识别精度不损失。
    """
    img = Image.open(image_path)
    w, h = img.size
    longest = max(w, h)
    if longest > MAX_VL_EDGE or os.path.getsize(image_path) > MAX_VL_BYTES:
        scale = min(1.0, MAX_VL_EDGE / longest)
        if scale < 1.0:
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ============ 通道 1：通义千问 VL（OpenAI 兼容接口） ============

def _call_dashscope_vl(image_path: str, prompt: str, cfg: dict) -> str:
    """用 dashscope 兼容模式的多模态接口识别图片，返回文本；失败抛异常。"""
    api_key = (cfg.get("api_key") or "").strip()
    if not api_key:
        raise RuntimeError("未配置 DASHSCOPE_API_KEY")
    model = (cfg.get("model") or "qwen-vl-plus").strip()
    url = (cfg.get("base_url") or
           "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions").strip()

    b64 = _prepare_image_b64(image_path)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    # 不走系统代理：图片直连更稳（避免 7897 端口代理 RST）
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


# ============ 通道 2：智谱 GLM 视觉（OpenAI 兼容接口） ============

def _call_glm_vl(image_path: str, prompt: str, cfg: dict) -> str:
    """用智谱 GLM 视觉模型识别图片，返回文本；失败抛异常。"""
    api_key = (cfg.get("api_key") or "").strip()
    if not api_key:
        raise RuntimeError("未配置 GLM_API_KEY")
    model = (cfg.get("model") or "glm-4.6v-flash").strip()
    url = (cfg.get("base_url") or
           "https://open.bigmodel.cn/api/paas/v4/chat/completions").strip()

    b64 = _prepare_image_b64(image_path)

    # 对齐官方 SDK（zai）：data URI 前缀 + JPEG base64；大图已压缩，避免 400
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    # 不走系统代理：图片直连更稳（避免本地代理 RST）
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


# ============ 通道 3：本地 Ollama 视觉模型 ============

def _call_ollama_vl(image_path: str, prompt: str, cfg: dict) -> str:
    """用本地 Ollama 视觉模型识别图片，返回文本；失败抛异常。"""
    model = (cfg.get("model") or "").strip()
    if not model:
        raise RuntimeError("未配置 IMAGE_VL_MODEL")
    url = (cfg.get("base_url") or "http://localhost:11434/api/chat").strip()

    b64 = _prepare_image_b64(image_path)

    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [b64],
            }
        ],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("message", {}).get("content", "")


def _short_err(e: Exception) -> str:
    """把异常压缩成一句可读提示，重点识别限流/鉴权/网络错误。"""
    s = str(e)
    if "429" in s or "请求过多" in s or "稍后再试" in s:
        return "服务端限流(429)，稍后重试"
    if "401" in s or "unauthorized" in s.lower() or "invalid" in s.lower():
        return "鉴权失败，请检查 API Key"
    if "400" in s:
        return "请求参数错误(400)"
    if "getaddrinfo" in s or "Connection" in s or "timed out" in s or "URLError" in s:
        return "网络连接失败，请检查 base_url 与网络"
    return s[:120]


# ============ 主工具 ============

@tool(
    description="""
    图片解析工具，分析用户上传的图片信息
    提取：图片格式、尺寸、颜色模式、主色调、文件大小
    识别：图片内容（人物/动物/场景/文字/物体等）
    参数：image_path 本地图片路径
    返回：结构化图片信息 + 内容描述
    """
)
def image_analyze(image_path: str) -> str:
    """图片解析：PIL 基础信息 + 多模态内容识别（云端/本地可配置，失败自动降级）。"""
    try:
        if not os.path.exists(image_path):
            return "错误：图片文件不存在"

        basic = _extract_basic_info(image_path)
        prompt = "详细描述这张图片：场景、物体、人物、文字、氛围"

        vl_cfg = _resolve_vl_config()
        provider = vl_cfg.get("provider", "")

        # 按 provider 选择通道；都失败则降级为仅基础信息
        content = None
        err_note = ""
        if provider == "dashscope":
            try:
                content = _call_dashscope_vl(image_path, prompt, vl_cfg)
            except Exception as e:
                err_note = f"（dashscope 识别失败：{_short_err(e)}）"
        elif provider == "glm":
            try:
                content = _call_glm_vl(image_path, prompt, vl_cfg)
            except Exception as e:
                err_note = f"（GLM 识别失败：{_short_err(e)}）"
        elif provider == "ollama":
            try:
                content = _call_ollama_vl(image_path, prompt, vl_cfg)
            except Exception as e:
                err_note = f"（Ollama 识别失败：{_short_err(e)}）"
        else:
            err_note = "（未启用：未配置图片解析模型；请在系统设置里配置云端 VL 或本地 Ollama 视觉）"

        if content:
            return basic + "\n\n===== 图片内容识别 =====\n" + str(content)

        # 全失败/未配置：降级为仅基础信息，带上失败原因便于定位
        return basic + "\n\n===== 图片内容识别 =====\n" + err_note

    except Exception as e:
        return f"图片解析异常：{str(e)}"
