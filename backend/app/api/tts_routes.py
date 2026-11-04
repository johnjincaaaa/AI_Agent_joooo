"""
TTS 路由 —— 记忆体语音（多厂商中转适配层）。

前端通过本路由调用用户选择的语音通道：
  - voicestudio（本地 127.0.0.1:3900）
  - doubao（豆包 TTS 2.0，火山引擎）
  - cosyvoice（通义 CosyVoice，阿里云百炼）
  - glm（智谱 GLM-TTS）

语音厂商互斥：用户一次只能选一个 provider。路由层读用户数据库 voice 配置，
经 registry 取对应适配器，业务代码不感知厂商差异。

依赖：app/services/voice/（base + 4 适配文件 + registry）。
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.token_utils import verify_token
from app.core.db import get_db
from app.api.ai_config_routes import get_user_ai_config, save_user_ai_config
from app.services.voice.registry import get_provider, list_providers

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
    format: str = "wav"
    language: Optional[str] = None
    speed: float = 1.0


def _current_provider(user_id: int, db: Session):
    """读用户 voice 配置，实例化对应适配器。"""
    cfg = get_user_ai_config(db, user_id).get("voice") or {}
    provider_id = (cfg.get("provider") or "voicestudio").strip()
    return get_provider(provider_id, cfg), provider_id, cfg


@router.get("/ai/tts/providers", summary="语音厂商列表 + 当前选择")
def tts_providers(
    user_id: int = Depends(verify_token),
    db: Session = Depends(get_db),
):
    cfg = get_user_ai_config(db, user_id).get("voice") or {}
    return {
        "ok": True,
        "providers": list_providers(),
        "current": (cfg.get("provider") or "voicestudio").strip(),
        "config": cfg,
    }


@router.get("/ai/tts/health", summary="当前语音通道健康检查")
def tts_health(
    user_id: int = Depends(verify_token),
    db: Session = Depends(get_db),
):
    provider, pid, _ = _current_provider(user_id, db)
    if pid == "voicestudio":
        from app.services import tts_client
        return {"provider": pid, **tts_client.check_health()}
    result = provider.test()
    return {"provider": pid, **result}


@router.get("/ai/tts/voices", summary="枚举当前语音通道可用音色")
def tts_voices(
    user_id: int = Depends(verify_token),
    db: Session = Depends(get_db),
):
    provider, pid, cfg = _current_provider(user_id, db)
    ok, voices, err = provider.list_voices()
    if not ok:
        return {"ok": True, "voices": [], "warning": err, "provider": pid}
    cloned = cfg.get("cloned_voices") or []
    for cv in cloned:
        if isinstance(cv, dict) and cv.get("voice_id"):
            voices.append({
                "voice_id": cv["voice_id"],
                "name": cv.get("name") or cv["voice_id"],
                "type": "cloned",
            })
    return {"ok": True, "voices": voices, "provider": pid}


@router.post("/ai/tts/synthesize", summary="文本合成语音（当前语音通道）")
def tts_synthesize(
    body: SynthesizeReq,
    user_id: int = Depends(verify_token),
    db: Session = Depends(get_db),
):
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="合成文本不能为空")
    if len(text) > 4096:
        raise HTTPException(status_code=400, detail="文本过长（<=4096字）")
    fmt = body.format if body.format in _FORMAT_MIME else "wav"
    provider, pid, _ = _current_provider(user_id, db)
    ok, audio, err = provider.synthesize(
        text=text, voice=body.voice, fmt=fmt,
        language=body.language, speed=body.speed,
    )
    if not ok:
        raise HTTPException(status_code=502, detail=f"语音合成失败：{err}")
    return Response(
        content=audio,
        media_type=_FORMAT_MIME.get(fmt, "audio/wav"),
        headers={"Content-Disposition": f'inline; filename="speech.{fmt}"'},
    )


@router.post("/ai/tts/clone", summary="克隆音色（当前语音通道，成功后保存 voice_id）")
async def tts_clone(
    file: UploadFile = File(...),
    name: str = Form(...),
    ref_text: str = Form(""),
    language: str = Form("zh"),
    user_id: int = Depends(verify_token),
    db: Session = Depends(get_db),
):
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="音色名称不能为空")
    if len(name) > 50:
        raise HTTPException(status_code=400, detail="音色名称过长（<=50字）")
    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="录音内容为空")

    provider, pid, cfg = _current_provider(user_id, db)
    ok, profile, err = provider.clone_voice(
        name=name, audio=audio, filename=file.filename or "reference.wav",
        ref_text=(ref_text or "").strip(),
    )
    if not ok:
        raise HTTPException(status_code=502, detail=f"克隆失败：{err}")

    vid = profile.get("voice_id") or ""
    if vid:
        cloned = list(cfg.get("cloned_voices") or [])
        if not any(isinstance(c, dict) and c.get("voice_id") == vid for c in cloned):
            cloned.append({"voice_id": vid, "name": profile.get("name") or name, "provider": pid})
        save_user_ai_config(db, user_id, {"voice": {"cloned_voices": cloned}})

    return {
        "ok": True,
        "voice_id": vid,
        "name": profile.get("name") or name,
        "profile": profile,
        "provider": pid,
    }


@router.post("/ai/tts/transcribe", summary="音频转文字（当前语音通道）")
async def tts_transcribe(
    file: UploadFile = File(...),
    model: str = Form(""),
    response_format: str = Form("json"),
    user_id: int = Depends(verify_token),
    db: Session = Depends(get_db),
):
    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="音频内容为空")
    provider, pid, _ = _current_provider(user_id, db)
    ok, text, err = provider.transcribe(audio, filename=file.filename or "audio.wav")
    if not ok:
        raise HTTPException(status_code=502, detail=f"转录失败：{err}")
    return {"ok": True, "text": text, "provider": pid}


class VoiceTestReq(BaseModel):
    """测试语音通道时允许传表单当前值覆盖，未传则用数据库已保存配置。"""
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    app_id: Optional[str] = None
    access_token: Optional[str] = None
    voice_id: Optional[str] = None


@router.post("/ai/tts/test", summary="语音通道连通性测试（TTS 合成 + STT 转写）")
def tts_test(
    body: Optional[VoiceTestReq] = None,
    user_id: int = Depends(verify_token),
    db: Session = Depends(get_db),
):
    provider, pid, cfg = _current_provider(user_id, db)
    # body 覆盖：填了哪个字段用哪个，否则回退数据库配置
    if body is not None:
        override = {k: v for k, v in {
            "provider": body.provider,
            "model": body.model,
            "api_key": body.api_key,
            "app_id": body.app_id,
            "access_token": body.access_token,
            "voice_id": body.voice_id,
        }.items() if v}
        if override:
            merged = dict(cfg)
            merged.update(override)
            pid = (override.get("provider") or pid).strip()
            provider = get_provider(pid, merged)
    result = provider.test()
    return {"ok": True, "provider": pid, **result}
