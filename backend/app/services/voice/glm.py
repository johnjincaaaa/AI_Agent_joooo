"""
智谱 GLM-TTS 适配器 —— 智谱开放平台（open.bigmodel.cn）。

凭据（cfg）：
  - api_key:  智谱 API Key
  - model:    TTS 模型名，默认 glm-4-voice（以官方文档为准）
  - voice_id: 默认音色（如 xiaozhi / xiaowei 等官方音色）

接口（智谱开放平台，endpoint 用 cfg.base_url 覆盖）：
  - TTS:  POST {base}/api/paas/v4/tts（返回音频）
  - STT:  POST {base}/api/paas/v4/asr（音频转文字）
  - 克隆: 智谱语音克隆走声音复刻接口（按官方开通）

注意：endpoint 与字段以智谱官方文档为准；这里按通用模式实现。
"""
import base64
import json
import time
import urllib.request
import urllib.error
from typing import List, Optional, Tuple

from app.services.voice.base import VoiceProvider


class GLMProvider(VoiceProvider):
    id = "glm"
    name = "智谱 GLM-TTS"

    DEFAULT_BASE = "https://open.bigmodel.cn"

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
        }

    def list_voices(self) -> Tuple[bool, List[dict], str]:
        ok, msg = self._check_cred()
        if not ok:
            return False, [], msg
        voices = [
            {"voice_id": "xiaozhi", "name": "小智（默认女声）", "type": "system"},
            {"voice_id": "xiaowei", "name": "小薇（女声）", "type": "system"},
        ]
        return True, voices, ""

    def synthesize(self, text: str, voice: str = "default", fmt: str = "wav",
                   speed: float = 1.0, language: Optional[str] = None) -> Tuple[bool, bytes, str]:
        ok, msg = self._check_cred()
        if not ok:
            return False, b"", msg
        voice = voice if voice and voice != "default" else self._default_voice()
        if not voice or voice == "default":
            voice = "xiaozhi"
        model = self._cfg("model") or "glm-4-voice"
        payload = {
            "model": model,
            "input": text,
            "voice": voice,
            "response_format": fmt if fmt in ("mp3", "wav") else "wav",
            "speed": float(speed or 1.0),
        }
        url = self._base() + "/api/paas/v4/tts"
        req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                     headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
        except urllib.error.HTTPError as e:
            return False, b"", e.read().decode("utf-8", errors="replace")[:200]
        except Exception as e:
            return False, b"", str(e)[:200]

        # 智谱可能直接返回音频二进制，或 JSON 里带 base64/url
        if data[:2] in (b"ID", b"RI") or data[:3] == b"\xff\xfb\x90":  # mp3/wav 魔数
            return True, data, ""
        try:
            parsed = json.loads(data.decode("utf-8"))
        except Exception:
            return True, data, ""  # 直接当音频
        b64 = (parsed.get("data") or {}).get("audio") or parsed.get("audio") or ""
        if b64:
            try:
                return True, base64.b64decode(b64), ""
            except Exception as e:
                return False, b"", f"GLM 音频解码失败：{e}"
        url_ = (parsed.get("data") or {}).get("url") or parsed.get("url") or ""
        if url_:
            try:
                with urllib.request.urlopen(url_, timeout=60) as resp:
                    return True, resp.read(), ""
            except Exception as e:
                return False, b"", f"GLM 音频下载失败：{e}"
        return False, b"", f"GLM 返回格式未识别：{str(parsed)[:200]}"

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.wav") -> Tuple[bool, str, str]:
        ok, msg = self._check_cred()
        if not ok:
            return False, "", msg
        boundary = "----glm-%d" % int(time.time() * 1000)
        parts = [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: audio/wav\r\n\r\n".encode("utf-8")
            + audio_bytes + b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
        body = b"".join(parts)
        url = self._base() + "/api/paas/v4/asr"
        req = urllib.request.Request(url, data=body, headers={
            "Authorization": f"Bearer {self._cfg('api_key')}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return False, "", e.read().decode("utf-8", errors="replace")[:200]
        except Exception as e:
            return False, "", str(e)[:200]
        text = (data.get("data") or {}).get("text") or data.get("text") or ""
        return (True, text, "") if text else (False, "", f"GLM ASR 返回为空：{str(data)[:200]}")

    def clone_voice(self, name: str, audio: bytes, filename: str = "reference.wav",
                    ref_text: str = "") -> Tuple[bool, dict, str]:
        ok, msg = self._check_cred()
        if not ok:
            return False, {}, msg
        # 智谱声音复刻：上传参考音频 + 名称，返回 voice_id。
        # 端点用 cfg.base_url 覆盖；字段以智谱官方 voice clone 接口为准。
        url = self._base() + "/api/paas/v4/voice-clone"
        boundary = "----glm-clone-%d" % int(time.time() * 1000)
        parts = [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"name\"\r\n\r\n{name}\r\n".encode("utf-8"),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n{self._cfg('model') or 'glm-4-voice'}\r\n".encode("utf-8"),
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
        }, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return False, {}, e.read().decode("utf-8", errors="replace")[:200]
        except Exception as e:
            return False, {}, str(e)[:200]

        out = data.get("data") or data.get("output") or {}
        vid = (out.get("voice_id") or out.get("voiceId") or out.get("speaker_id")
               or data.get("voice_id") or data.get("voiceId") or data.get("speaker_id") or "")
        if not vid:
            return False, {}, f"智谱复刻返回未识别到 voice_id：{str(data)[:200]}"
        return True, {"voice_id": vid, "name": name}, ""
