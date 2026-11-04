"""
语音通道注册表 —— 按 provider 取适配器。

新增语音厂商只需：
  1. 在 voice/ 下写一个继承 VoiceProvider 的适配文件
  2. 在这里注册进 PROVIDERS
路由层无需改动。
"""
from typing import Dict, Type

from app.services.voice.base import VoiceProvider
from app.services.voice.voicestudio import VoiceStudioProvider
from app.services.voice.doubao import DoubaoProvider
from app.services.voice.cosyvoice import CosyVoiceProvider
from app.services.voice.glm import GLMProvider

PROVIDERS: Dict[str, Type[VoiceProvider]] = {
    "voicestudio": VoiceStudioProvider,
    "doubao": DoubaoProvider,
    "cosyvoice": CosyVoiceProvider,
    "glm": GLMProvider,
}

# provider id -> 展示名（前端下拉也用）
PROVIDER_LABELS = {v.id: v.name for v in PROVIDERS.values()}


def get_provider(provider_id: str, cfg: dict = None) -> VoiceProvider:
    """按 provider_id 实例化适配器；未知 provider 回退 voicestudio。"""
    cls = PROVIDERS.get((provider_id or "").strip()) or VoiceStudioProvider
    return cls(cfg or {})


def list_providers() -> list:
    return [{"id": pid, "name": p.name} for pid, p in PROVIDERS.items()]
