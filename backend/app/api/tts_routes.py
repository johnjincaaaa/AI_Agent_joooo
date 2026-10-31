"""
TTS 路由 —— 记忆体语音（VoiceStudio 本地语音服务代理）。

前端通过本路由调用本机 VoiceStudio（127.0.0.1:3900）：
- 合成语音（文本 → 音频）
- 枚举音色（记忆体音色绑定）
- 健康检查（判断服务是否装好）

依赖：app/services/tts_client.py（零依赖 HTTP 直连）。
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.token_utils import verify_token
from app.services import tts_client

logger = logging.getLogger(__name__)
router = APIRouter()

# 格式 → MIME 映射
_FORMAT_MIME = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "opus": "audio/ogg",
    "ogg": "audio/ogg",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "pcm": "audio/pcm",
}


class SynthesizeReq(BaseModel):
    text: str
    voice: str = "default"
    format: str = "wav"          # wav/mp3/opus/ogg/aac/flac/pcm
    language: Optional[str] = None
    speed: float = 1.0


class TranscribeReq(BaseModel):
    filename: str = "audio.wav"
    # audio 二进制通过 multipart 上传，这里用 bytes 接收（前端 fetch FormData）
    response_format: str = "json"


@router.get("/ai/tts/health", summary="VoiceStudio 服务健康检查")
def tts_health(user_id: int = Depends(verify_token)):
    return tts_client.check_health()


@router.get("/ai/tts/voices", summary="枚举 VoiceStudio 可用音色")
def tts_voices(user_id: int = Depends(verify_token)):
    voices = tts_client.list_voices()
    return {"ok": True, "voices": voices}


@router.post("/ai/tts/synthesize", summary="文本合成语音（返回音频二进制）")
def tts_synthesize(body: SynthesizeReq, user_id: int = Depends(verify_token)):
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="合成文本不能为空")
    if len(text) > 4096:
        raise HTTPException(status_code=400, detail="文本过长（<=4096字）")
    fmt = body.format if body.format in _FORMAT_MIME else "wav"
    ok, audio, err = tts_client.synthesize(
        text=text,
        voice=body.voice,
        fmt=fmt,
        language=body.language,
        speed=body.speed,
    )
    if not ok:
        raise HTTPException(status_code=502, detail=f"语音合成失败：{err}")
    return Response(
        content=audio,
        media_type=_FORMAT_MIME.get(fmt, "audio/wav"),
        headers={"Content-Disposition": f'inline; filename="speech.{fmt}"'},
    )


@router.post("/ai/tts/clone", summary="克隆音色（上传参考录音生成专属音色）")
async def tts_clone(
    file: UploadFile = File(...),
    name: str = Form(...),
    ref_text: str = Form(""),
    language: str = Form("zh"),
    user_id: int = Depends(verify_token),
):
    """上传一段有授权的参考录音 → 克隆出专属音色 profile，返回音色 ID。"""
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="音色名称不能为空")
    if len(name) > 50:
        raise HTTPException(status_code=400, detail="音色名称过长（<=50字）")
    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="录音内容为空")
    ok, profile, err = tts_client.clone_voice(
        name=name, audio=audio, filename=file.filename or "reference.wav",
        ref_text=(ref_text or "").strip(), language=language or "zh",
    )
    if not ok:
        raise HTTPException(status_code=502, detail=f"克隆失败：{err}")
    return {
        "ok": True,
        "voice_id": profile.get("id") or profile.get("voice_id") or profile.get("name"),
        "name": profile.get("name", name),
        "profile": profile,
    }


@router.post("/ai/tts/transcribe", summary="音频转文字（语音发消息）")
async def tts_transcribe(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    response_format: str = Form("json"),
    user_id: int = Depends(verify_token),
):
    """音频 → 文字（646 语言）。前端上传录音文件，返回转录文本。"""
    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="音频内容为空")
    ok, text, err = tts_client.transcribe(
        audio, filename=file.filename or "audio.wav",
        response_format=response_format, model=model,
    )
    if not ok:
        raise HTTPException(status_code=502, detail=f"转录失败：{err}")
    return {"ok": True, "text": text}
