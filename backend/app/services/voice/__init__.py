"""
语音多厂商适配层。

用法：
    from app.services.voice.registry import get_provider, list_providers
    provider = get_provider("doubao", user_voice_cfg)
    ok, audio, err = provider.synthesize("你好", voice="default")
"""
from app.services.voice.registry import get_provider, list_providers, PROVIDERS, PROVIDER_LABELS  # noqa: F401
from app.services.voice.base import VoiceProvider  # noqa: F401
