"""
豆包 TTS 2.0 适配器 —— 火山引擎语音技术（OpenSpeech HTTP API）。

凭据（cfg）：
  - app_id:        火山引擎应用 APPID
  - access_token:  应用 Access Token
  - model:         集群名，默认 volcano_tts（可按官方文档改，如 volcano_tts 2.0）
  - voice_id:      默认音色类型（如 zh_female_tianmei），存为默认 voice_type

接口（以火山引擎官方文档为准，这里按 OpenSpeech HTTP 模式实现）：
  - TTS:  POST https://openspeech.bytedance.com/api/v1/tts
  - 克隆: POST https://openspeech.bytedance.com/api/v1/mega_tts/audio/upload（返回 speaker_id）
  - STT:  走录音文件识别（需按官方开通）；此处实现 HTTP 一次性识别接口占位。

注意：豆包 ASR 官方主要走 WebSocket 流式；本适配器 STT 提供 HTTP 录音文件识别，
端点可在 cfg.base_url 覆盖。测试前请按官方文档核对 endpoint 与参数。
"""
import base64
import json
import time
import urllib.request
import urllib.error
import uuid
from typing import List, Optional, Tuple

from app.services.voice.base import VoiceProvider


class DoubaoProvider(VoiceProvider):
    id = "doubao"
    name = "豆包 TTS 2.0"

    DEFAULT_BASE = "https://openspeech.bytedance.com"

    def _base(self) -> str:
        return (self.cfg.get("base_url") or self.DEFAULT_BASE).rstrip("/")

    def _auth_header(self) -> str:
        token = self._cfg("access_token")
        return f"Bearer;{token}"

    def _check_cred(self) -> Tuple[bool, str]:
        if not self._cfg("app_id"):
            return False, "未填写 APPID"
        if not self._cfg("access_token"):
            return False, "未填写 Access Token"
        return True, ""

    def _post_json(self, path: str, payload: dict, timeout: int = 60) -> Tuple[int, dict, str]:
        url = self._base() + path
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": self._auth_header(),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8")), ""
        except urllib.error.HTTPError as e:
            return e.code, {}, e.read().decode("utf-8", errors="replace")[:200]
        except Exception as e:
            return -1, {}, str(e)[:200]

    def list_voices(self) -> Tuple[bool, List[dict], str]:
        # 火山引擎音色列表接口；未开通/未接入时返回空列表 + 提示手动填 voice_type
        ok, msg = self._check_cred()
        if not ok:
            return False, [], msg
        # 火山引擎音色列表需要单独开通「音色列表」能力；这里给出系统常用音色占位，
        # 用户可在系统设置里直接填 voice_type（voice_id 字段）。
        voices = [
            {"voice_id": "zh_female_tianmei", "name": "甜美（默认女声）", "type": "system"},
            {"voice_id": "zh_male_qingse", "name": "青涩（男声）", "type": "system"},
            {"voice_id": "zh_female_wanwan", "name": "晚晚（女声）", "type": "system"},
        ]
        return True, voices, ""

    def synthesize(self, text: str, voice: str = "default", fmt: str = "wav",
                   speed: float = 1.0, language: Optional[str] = None) -> Tuple[bool, bytes, str]:
        ok, msg = self._check_cred()
        if not ok:
            return False, b"", msg
        voice_type = voice if voice and voice != "default" else self._default_voice()
        if not voice_type or voice_type == "default":
            voice_type = "zh_female_tianmei"
        # 火山引擎音频编码：mp3 / wav；把 fmt 映射为火山编码
        encoding = "mp3" if fmt in ("mp3",) else "wav"
        payload = {
            "app": {
                "appid": self._cfg("app_id"),
                "token": self._cfg("access_token"),
                "cluster": self._cfg("model") or "volcano_tts",
            },
            "user": {"uid": f"jingent_{self._cfg('app_id')}"},
            "audio": {
                "voice_type": voice_type,
                "encoding": encoding,
                "speed_ratio": float(speed or 1.0),
            },
            "request": {
                "reqid": uuid.uuid4().hex,
                "text": text,
                "operation": "query",
            },
        }
        status, data, err = self._post_json("/api/v1/tts", payload, timeout=120)
        if status != 200:
            return False, b"", err or f"豆包 TTS 失败 status={status}"
        if data.get("code") not in (3000, 0):
            return False, b"", f"豆包 TTS 业务错误：{data.get('message') or data.get('code')}"
        # 返回 base64 音频
        b64 = data.get("data") or ""
        if not b64:
            return False, b"", "豆包 TTS 返回空音频"
        try:
            return True, base64.b64decode(b64), ""
        except Exception as e:
            return False, b"", f"豆包 TTS 音频解码失败：{e}"

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.wav") -> Tuple[bool, str, str]:
        ok, msg = self._check_cred()
        if not ok:
            return False, "", msg
        # 火山引擎一句话识别（HTTP 一次性）。
        # 官方主推 WebSocket 流式；此 HTTP 端点用 cfg.base_url 覆盖，字段以官方文档为准。
        # 如需走录音文件识别：改成 /api/v1/asr/submit 提交 + /api/v1/asr/query 轮询两步。
        url = self._base() + "/api/v1/asr"
        boundary = "----doubao-asr-%d" % int(time.time() * 1000)
        app_json = json.dumps({
            "appid": self._cfg("app_id"),
            "token": self._cfg("access_token"),
            "cluster": self._cfg("model") or "volcengine_streaming_common",
        }, ensure_ascii=False)
        req_json = json.dumps({"model": "bigmodel", "language": "zh-CN"}, ensure_ascii=False)
        parts = [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"app\"\r\n\r\n{app_json}\r\n".encode("utf-8"),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"request\"\r\n\r\n{req_json}\r\n".encode("utf-8"),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"audio\"; filename=\"{filename}\"\r\nContent-Type: audio/wav\r\n\r\n".encode("utf-8")
            + audio_bytes + b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
        body = b"".join(parts)
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": self._auth_header(),
        }, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return False, "", e.read().decode("utf-8", errors="replace")[:200]
        except Exception as e:
            return False, "", str(e)[:200]

        # 先取文本，有就成功；没有再看业务错误码
        result = data.get("result") or data.get("text") or ""
        text = ""
        if isinstance(result, dict):
            text = result.get("text") or result.get("utterances") or ""
            if isinstance(text, list):
                text = " ".join(str(t) for t in text)
        else:
            text = str(result)
        text = (text or "").strip()
        if text:
            return True, text, ""
        code = data.get("code")
        if code not in (1000, 0, None):
            return False, "", f"豆包 ASR 业务错误：{data.get('message') or code}"
        return False, "", f"豆包 ASR 返回为空：{str(data)[:200]}"

    def clone_voice(self, name: str, audio: bytes, filename: str = "reference.wav",
                    ref_text: str = "") -> Tuple[bool, dict, str]:
        ok, msg = self._check_cred()
        if not ok:
            return False, {}, msg
        url = self._base() + "/api/v1/mega_tts/audio/upload"
        boundary = "----doubao-%d" % int(time.time() * 1000)
        parts = [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: audio/wav\r\n\r\n".encode("utf-8")
            + audio + b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
        body = b"".join(parts)
        req = urllib.request.Request(
            url, data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Authorization": self._auth_header(),
                "Resource-Id": "volc.megatts.voiceclone",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return False, {}, e.read().decode("utf-8", errors="replace")[:200]
        except Exception as e:
            return False, {}, str(e)[:200]
        speaker_id = data.get("speaker_id") or data.get("voice_id") or ""
        if not speaker_id:
            return False, {}, f"豆包克隆失败：{data.get('message') or data}"
        return True, {"voice_id": speaker_id, "name": name}, ""
