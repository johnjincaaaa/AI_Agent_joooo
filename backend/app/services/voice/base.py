"""
语音通道统一接口（Voice Provider 适配层）。

每个语音厂商（voicestudio / 豆包 / 通义 CosyVoice / 智谱 GLM-TTS）实现同一个
接口，路由层通过 registry 按用户选择的 provider 取适配器，业务代码不关心底层差异。

统一方法约定（返回 Tuple[bool, data, err]）：
  - list_voices()  -> (ok, [{"voice_id","name","type"}], err)
  - synthesize(text, voice, fmt, speed, language) -> (ok, audio_bytes, err)
  - transcribe(audio_bytes, filename) -> (ok, text, err)
  - clone_voice(name, audio, filename, ref_text) -> (ok, {"voice_id","name"}, err)
  - test() -> {"ok", "tts", "stt", "detail"}   # 连通性测试（合成 + 转写）
"""
from typing import List, Optional, Tuple


class VoiceProvider:
    """语音厂商适配器基类。子类实现具体厂商接口。"""

    id: str = "base"
    name: str = "基础语音通道"

    def __init__(self, cfg: dict):
        # cfg = 用户 voice 配置 {provider, model, api_key, app_id, access_token, voice_id, cloned_voices}
        self.cfg = cfg or {}

    # ── 子类必须实现 ──────────────────────────────────────
    def list_voices(self) -> Tuple[bool, List[dict], str]:
        raise NotImplementedError

    def synthesize(self, text: str, voice: str = "default", fmt: str = "wav",
                   speed: float = 1.0, language: Optional[str] = None) -> Tuple[bool, bytes, str]:
        raise NotImplementedError

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.wav") -> Tuple[bool, str, str]:
        raise NotImplementedError

    def clone_voice(self, name: str, audio: bytes, filename: str = "reference.wav",
                    ref_text: str = "") -> Tuple[bool, dict, str]:
        raise NotImplementedError

    # ── 通用测试：合成一段固定文本 + 转写自身合成音频 ──────
    def test(self) -> dict:
        """连通性测试：TTS 合成成功 + STT 转写成功才算全通。"""
        result = {"ok": False, "tts": False, "stt": False, "detail": ""}
        sample = "你好，我是你的智能语音助手"
        ok, audio, err = self.synthesize(sample, voice=self._default_voice(), fmt="wav")
        if not ok or not audio:
            result["detail"] = f"TTS 合成失败：{err[:120]}"
            return result
        result["tts"] = True
        ok2, text, err2 = self.transcribe(audio, "test.wav")
        if not ok2:
            result["detail"] = f"STT 转写失败：{err2[:120]}"
            return result
        result["stt"] = True
        result["ok"] = True
        result["detail"] = f"TTS+STT 均通过，转写结果：{text[:80]}"
        return result

    def _default_voice(self) -> str:
        return (self.cfg.get("voice_id") or "default").strip()

    def _cfg(self, key: str, default: str = "") -> str:
        return (self.cfg.get(key) or default).strip()
