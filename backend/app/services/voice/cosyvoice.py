"""
通义 CosyVoice 适配器 —— 阿里云百炼（DashScope）。

凭据（cfg）：
  - api_key:    DashScope API Key（sk-...）
  - model:      模型名，默认 cosyvoice-v1
  - voice_id:   默认音色（如 longxiaochun / longcheng 等官方音色名）

接口（DashScope 官方，endpoint 可用 cfg.base_url 覆盖）：
  - TTS:  POST {base}/api/v1/services/aigc/multimodal-generation/generation
          或 CosyVoice HTTP: POST {base}/api/v1/services/aigc/tts?model=cosyvoice-v1
  - STT:  POST {base}/api/v1/services/audio/asr/recognition（Paraformer）
  - 克隆: CosyVoice 音色复刻走 voice clone 上传（按官方开通）

注意：endpoint 与字段以阿里云百炼官方文档为准；这里按通用 DashScope 模式实现。
"""
import base64
import json
import time
import urllib.request
import urllib.error
from typing import List, Optional, Tuple

from app.services.voice.base import VoiceProvider


class CosyVoiceProvider(VoiceProvider):
    id = "cosyvoice"
    name = "通义 CosyVoice"

    DEFAULT_BASE = "https://dashscope.aliyuncs.com"

    def _base(self) -> str:
        return (self.cfg.get("base_url") or self.DEFAULT_BASE).rstrip("/")

    def _check_cred(self) -> Tuple[bool, str]:
        if not self._cfg("api_key"):
            return False, "未填写 API Key"
        return True, ""

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._cfg('api_key')}",
            "Content-Type": "application/json",
            "X-DashScope-DataInspection": "disable",
        }

    def list_voices(self) -> Tuple[bool, List[dict], str]:
        ok, msg = self._check_cred()
        if not ok:
            return False, [], msg
        # CosyVoice 官方音色（可在百炼控制台查看全部）；给出常用默认音色
        voices = [
            {"voice_id": "longxiaochun", "name": "龙小春（女声）", "type": "system"},
            {"voice_id": "longcheng", "name": "龙诚（男声）", "type": "system"},
            {"voice_id": "longhuayu", "name": "龙华宇（男声）", "type": "system"},
        ]
        return True, voices, ""

    def synthesize(self, text: str, voice: str = "default", fmt: str = "wav",
                   speed: float = 1.0, language: Optional[str] = None) -> Tuple[bool, bytes, str]:
        ok, msg = self._check_cred()
        if not ok:
            return False, b"", msg
        voice = voice if voice and voice != "default" else self._default_voice()
        if not voice or voice == "default":
            voice = "longxiaochun"
        model = self._cfg("model") or "cosyvoice-v1"
        fmt = fmt if fmt in ("wav", "mp3", "pcm") else "wav"

        payload = {
            "model": model,
            "input": {"text": text},
            "parameters": {"voice": voice, "format": fmt, "speed": float(speed or 1.0)},
        }
        url = self._base() + "/api/v1/services/aigc/multimodal-generation/generation"
        req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                     headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return False, b"", e.read().decode("utf-8", errors="replace")[:200]
        except Exception as e:
            return False, b"", str(e)[:200]

        # 提取音频：优先 base64 字段，其次 url 下载
        out = data.get("output") or {}
        audio = out.get("audio") or {}
        b64 = audio.get("data") or audio.get("audio") or out.get("data") or ""
        if b64:
            try:
                return True, base64.b64decode(b64), ""
            except Exception as e:
                return False, b"", f"CosyVoice 音频解码失败：{e}"
        audio_url = audio.get("url") or out.get("url") or ""
        if audio_url:
            try:
                with urllib.request.urlopen(audio_url, timeout=60) as resp:
                    return True, resp.read(), ""
            except Exception as e:
                return False, b"", f"CosyVoice 音频下载失败：{e}"
        return False, b"", f"CosyVoice 返回格式未识别：{str(data)[:200]}"

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.wav") -> Tuple[bool, str, str]:
        ok, msg = self._check_cred()
        if not ok:
            return False, "", msg
        boundary = "----cosy-%d" % int(time.time() * 1000)
        parts = [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: audio/wav\r\n\r\n".encode("utf-8")
            + audio_bytes + b"\r\n",
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\nparaformer-v2\r\n".encode("utf-8"),
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
        body = b"".join(parts)
        url = self._base() + "/api/v1/services/audio/asr/recognition"
        req = urllib.request.Request(url, data=body, headers={
            "Authorization": f"Bearer {self._cfg('api_key')}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-DashScope-DataInspection": "disable",
        }, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return False, "", e.read().decode("utf-8", errors="replace")[:200]
        except Exception as e:
            return False, "", str(e)[:200]
        text = ""
        try:
            out = data.get("output") or {}
            text = out.get("text") or (out.get("results") or [{}])[0].get("text") or ""
        except Exception:
            text = ""
        return (True, text, "") if text else (False, "", f"CosyVoice ASR 返回为空：{str(data)[:200]}")

    def clone_voice(self, name: str, audio: bytes, filename: str = "reference.wav",
                    ref_text: str = "") -> Tuple[bool, dict, str]:
        ok, msg = self._check_cred()
        if not ok:
            return False, {}, msg
        # CosyVoice 音色复刻：上传参考音频 + 名称，返回专属 voice_id。
        # 端点用 cfg.base_url 覆盖；字段以阿里云百炼官方 voice clone 接口为准。
        url = self._base() + "/api/v1/services/aigc/voice-enrollment"
        boundary = "----cosy-clone-%d" % int(time.time() * 1000)
        parts = [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"name\"\r\n\r\n{name}\r\n".encode("utf-8"),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n{self._cfg('model') or 'cosyvoice-v1'}\r\n".encode("utf-8"),
        ]
        if ref_text:
            parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"text\"\r\n\r\n{ref_text}\r\n".encode("utf-8")
            )
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: audio/wav\r\n\r\n".encode("utf-8")
            + audio + b"\r\n"
        )
        parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        body = b"".join(parts)
        req = urllib.request.Request(url, data=body, headers={
            "Authorization": f"Bearer {self._cfg('api_key')}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-DashScope-DataInspection": "disable",
        }, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return False, {}, e.read().decode("utf-8", errors="replace")[:200]
        except Exception as e:
            return False, {}, str(e)[:200]

        out = data.get("output") or data.get("data") or {}
        vid = (out.get("voice_id") or out.get("voiceId") or out.get("speaker_id")
               or data.get("voice_id") or data.get("voiceId") or data.get("speaker_id") or "")
        if not vid:
            return False, {}, f"CosyVoice 复刻返回未识别到 voice_id：{str(data)[:200]}"
        return True, {"voice_id": vid, "name": name}, ""
