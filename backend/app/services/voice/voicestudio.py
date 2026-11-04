"""
VoiceStudio 适配器 —— 本地语音服务（127.0.0.1:3900，OmniVoice 引擎）。

复用 app.services.tts_client 的 HTTP 直连逻辑，包装成统一 VoiceProvider 接口。
无需 key（本地 loopback）；cfg.voice_id 可指定默认音色。
"""
from typing import List, Optional, Tuple

from app.services import tts_client
from app.services.voice.base import VoiceProvider


class VoiceStudioProvider(VoiceProvider):
    id = "voicestudio"
    name = "VoiceStudio（本地）"

    def list_voices(self) -> Tuple[bool, List[dict], str]:
        try:
            voices = tts_client.list_voices()
            return True, voices, ""
        except Exception as e:
            return False, [], str(e)[:200]

    def synthesize(self, text: str, voice: str = "default", fmt: str = "wav",
                   speed: float = 1.0, language: Optional[str] = None) -> Tuple[bool, bytes, str]:
        return tts_client.synthesize(
            text=text, voice=voice or self._default_voice(), fmt=fmt,
            language=language, speed=speed,
        )

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.wav") -> Tuple[bool, str, str]:
        return tts_client.transcribe(audio_bytes, filename=filename)

    def clone_voice(self, name: str, audio: bytes, filename: str = "reference.wav",
                    ref_text: str = "") -> Tuple[bool, dict, str]:
        ok, profile, err = tts_client.clone_voice(
            name=name, audio=audio, filename=filename, ref_text=ref_text,
        )
        if not ok:
            return False, {}, err
        return True, {
            "voice_id": profile.get("id") or profile.get("voice_id") or profile.get("name"),
            "name": profile.get("name", name),
        }, ""
