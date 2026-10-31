"""
VoiceStudio 本地语音客户端 —— 通过 HTTP 直连调用本机 VoiceStudio 服务。

VoiceStudio 是一个本地语音服务（Electron App + Python 后端，OmniVoice / k2-fsa 引擎），
默认监听 127.0.0.1:3900，提供 OpenAI 兼容 REST API + MCP 服务器。

本模块零依赖（只用标准库 urllib），负责：
- synthesize()：文本 → 语音音频（WAV/Ogg/Opus 等）
- list_voices()：枚举可用音色（含用户保存的 voice profile）
- check_health()：探测服务是否存活
- design_voice() / describe_voice()：文字描述设计音色（可选）

关键接口（来自 VoiceStudio 官方文档 docs/mcp.md 与 skills/voicestudio/SKILL.md）：
- POST /v1/audio/speech          → TTS（OpenAI 兼容）
- GET  /v1/audio/voices          → 音色列表
- POST /v1/audio/transcriptions  → STT（音频→文字）
- GET  /health                   → 健康检查

配置：默认连 http://127.0.0.1:3900（loopback，默认无认证）。
可通过环境变量 VOICESTUDIO_URL 覆盖（如远程后端）。
"""
import json
import logging
import time
import urllib.parse
import urllib.request
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# 默认地址：本机 loopback，VoiceStudio 默认端口
DEFAULT_BASE_URL = "http://127.0.0.1:3900"

# 每次请求超时（秒）。CPU 合成长文本较慢，给足时间；首调用还要下载 2.3GB 模型。
_DEFAULT_TIMEOUT = 180


def _base_url() -> str:
    import os
    return (os.getenv("VOICESTUDIO_URL") or DEFAULT_BASE_URL).rstrip("/")


def _request(method: str, path: str, payload: Optional[dict] = None,
             timeout: int = _DEFAULT_TIMEOUT, raw: bool = False,
             form: Optional[dict] = None, file_field: Optional[Tuple[str, str, bytes]] = None,
             file_field_name: str = "file"):
    """内部 HTTP 请求封装。返回 (status, body_bytes, content_type)。"""
    url = _base_url() + path
    headers = {"User-Agent": "jingent-tts/1.0"}
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif form is not None or file_field is not None:
        boundary = "----jingent-tts-%d" % int(time.time() * 1000)
        parts = []
        if file_field is not None:
            fname, ftype, fdata = file_field
            parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field_name}\"; filename=\"{fname}\"\r\n"
                f"Content-Type: {ftype}\r\n\r\n".encode("utf-8")
                + fdata + b"\r\n"
            )
        if form is not None:
            for k, v in form.items():
                parts.append(
                    f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n".encode("utf-8")
                    + str(v).encode("utf-8") + b"\r\n"
                )
        parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        body = b"".join(parts)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            return resp.status, data, resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:300]
        return e.code, err_body.encode("utf-8", errors="replace"), e.headers.get("Content-Type", "")
    except Exception as e:
        logger.warning("[tts-client] %s %s 请求失败: %s", method, path, e)
        return -1, str(e).encode("utf-8", errors="replace"), ""


def check_health() -> dict:
    """探测 VoiceStudio 服务是否存活。返回 {ok, status, detail}。"""
    status, data, _ = _request("GET", "/health", timeout=10)
    ok = status == 200
    detail = ""
    if status == 200:
        try:
            detail = json.loads(data.decode("utf-8", errors="replace"))
        except Exception:
            detail = data.decode("utf-8", errors="replace")[:200]
    elif status == -1:
        detail = data.decode("utf-8", errors="replace")[:200]
    return {"ok": ok, "status": status, "detail": detail}


def list_voices() -> List[dict]:
    """枚举可用音色。返回 [{"voice_id","name","type","language","id"}, ...]。"""
    status, data, _ = _request("GET", "/v1/audio/voices", timeout=30)
    if status != 200:
        logger.warning("[tts-client] list_voices 失败 status=%s", status)
        return []
    try:
        d = json.loads(data.decode("utf-8", errors="replace"))
        return d.get("voices", []) if isinstance(d, dict) else []
    except Exception as e:
        logger.warning("[tts-client] list_voices 解析失败: %s", e)
        return []


def clone_voice(name: str, audio: bytes, filename: str = "reference.wav",
                ref_text: str = "", language: str = "zh",
                timeout: int = 300) -> Tuple[bool, dict, str]:
    """克隆音色：上传一段参考录音，生成专属 voice profile。

    返回 (ok, profile_dict, error_msg)。profile_dict 含 id/name 等（id 即音色 ID）。
    - audio：参考录音二进制（wav/mp3/webm/ogg 等）
    - ref_text：录音对应的文字（可选；为空则 VoiceStudio 自动转录）
    - language：语言码（zh/en/...）
    """
    ftype = "audio/wav"
    fn = filename or "reference.wav"
    lower = fn.lower()
    if lower.endswith(".webm"):
        ftype = "audio/webm"
    elif lower.endswith(".mp3"):
        ftype = "audio/mpeg"
    elif lower.endswith(".ogg") or lower.endswith(".opus"):
        ftype = "audio/ogg"
    elif lower.endswith(".m4a"):
        ftype = "audio/mp4"
    status, data, _ = _request(
        "POST", "/profiles",
        form={"name": name, "kind": "clone", "ref_text": ref_text, "language": language},
        file_field=(fn, ftype, audio),
        file_field_name="ref_audio",
        timeout=timeout,
    )
    if status == 200:
        try:
            return True, json.loads(data.decode("utf-8", errors="replace")), ""
        except Exception:
            return True, {}, ""
    return False, {}, data.decode("utf-8", errors="replace")[:300]


def synthesize(text: str, voice: str = "default", fmt: str = "wav",
               language: Optional[str] = None, speed: float = 1.0,
               model: str = "omnivoice", timeout: int = _DEFAULT_TIMEOUT
               ) -> Tuple[bool, bytes, str]:
    """文本 → 语音音频。

    返回 (ok, audio_bytes, error_msg)。
    - text：合成文本（max 4096）
    - voice：音色 profile_id / 名字 / "default" / OpenAI 别名（alloy 等）
    - fmt：wav / mp3 / opus / ogg / aac / flac / pcm
    - language：ISO 639-1 语言码（None = 跟随 profile 语言）
    - speed：0.25 ~ 4.0
    """
    payload = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": fmt,
        "speed": speed,
    }
    if language:
        payload["language"] = language
    status, data, ctype = _request("POST", "/v1/audio/speech", payload=payload, timeout=timeout)
    if status == 200 and data:
        return True, data, ""
    err = ""
    try:
        err = data.decode("utf-8", errors="replace")[:300]
    except Exception:
        pass
    return False, b"", err or f"语音合成失败 (status={status})"


def transcribe(audio_bytes: bytes, filename: str = "audio.wav",
               response_format: str = "json", model: str = "whisper-1",
               timeout: int = 300) -> Tuple[bool, str, str]:
    """音频 → 文字（646 语言）。返回 (ok, text, error_msg)。"""
    # 根据文件名后缀推断 Content-Type（前端 MediaRecorder 是 webm/ogg/mp4）
    lower = (filename or "audio.wav").lower()
    if lower.endswith(".webm"):
        ctype = "audio/webm"
    elif lower.endswith(".ogg") or lower.endswith(".opus"):
        ctype = "audio/ogg"
    elif lower.endswith(".m4a") or lower.endswith(".mp4"):
        ctype = "audio/mp4"
    else:
        ctype = "audio/wav"
    status, data, _ = _request(
        "POST", "/v1/audio/transcriptions",
        file_field=(filename, ctype, audio_bytes),
        form={"model": model, "response_format": response_format},
        timeout=timeout,
    )
    if status == 200:
        try:
            raw = data.decode("utf-8", errors="replace")
            # VoiceStudio 返回 JSON（{"text": "..."}）或纯文本；统一提取纯文本
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and "text" in parsed:
                    return True, str(parsed["text"]), ""
                if isinstance(parsed, str):
                    return True, parsed, ""
                return True, raw, ""
            except Exception:
                return True, raw, ""
        except Exception:
            return True, "", ""
    return False, "", data.decode("utf-8", errors="replace")[:300]


def describe_voice(description: str, timeout: int = 60) -> Tuple[bool, dict, str]:
    """文字描述 → 设计属性（gender/age/pitch/style/accent），不保存。

    调用 VoiceStudio 的 POST /design/describe（确定性关键词映射，纯 CPU）。
    返回 (ok, attrs_dict, error_msg)，attrs_dict 含：
    {"attrs": {...}, "instruct": "...", "matched": [...], "unmatched": [...]}
    """
    status, data, _ = _request("POST", "/design/describe", payload={
        "description": description,
    }, timeout=timeout)
    if status == 200:
        try:
            return True, json.loads(data.decode("utf-8", errors="replace")), ""
        except Exception:
            return True, {}, ""
    return False, {}, data.decode("utf-8", errors="replace")[:200]


def design_voice(description: str, sample_text: str = "你好，我是你的专属音色",
                 language: Optional[str] = None, timeout: int = 180) -> Tuple[bool, dict, str]:
    """文字描述 → 直接生成一个 design 音色 profile（可保存复用）。

    返回 (ok, profile_dict, error_msg)。profile_dict 含 "id"（即音色 ID，可直接用于
    synthesize()）和 "name" 等字段。

    流程：
    1. POST /design/describe 把自由文字映射成 vd_states（design 参数空间）+ instruct；
    2. POST /profiles（kind=design）落库，服务端按 seed 渲染采样音频，音色身份稳定。
    """
    # 1. 文字 → 属性
    ok, attrs, err = describe_voice(description)
    if not ok:
        return False, {}, err
    vd_states = attrs.get("attrs") if isinstance(attrs, dict) else attrs
    instruct = attrs.get("instruct", "") if isinstance(attrs, dict) else ""
    if not isinstance(vd_states, dict) or not vd_states:
        return False, {}, f"无法从描述解析出音色属性：{description[:80]}"

    # 2. 属性 → design profile（kind=design，服务端渲染采样音频）
    name = (description.strip() or "设计音色")[:20] or "设计音色"
    status, data, _ = _request(
        "POST", "/profiles",
        form={
            "name": name,
            "kind": "design",
            "vd_states": json.dumps(vd_states, ensure_ascii=False),
            "instruct": instruct,
            "language": language or "zh",
            "ref_text": sample_text,
        },
        timeout=timeout,
    )
    if status == 200:
        try:
            return True, json.loads(data.decode("utf-8", errors="replace")), ""
        except Exception:
            return True, {}, ""
    return False, {}, f"设计音色失败 (status={status})：{data.decode('utf-8', errors='replace')[:200]}"
