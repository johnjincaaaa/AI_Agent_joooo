"""网页插件系统。"""
from app.plugins.base import PluginBase
from app.plugins.registry import PluginRegistry, get_registry

__all__ = ["PluginBase", "PluginRegistry", "get_registry"]
