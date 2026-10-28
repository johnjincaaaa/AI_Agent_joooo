"""
插件注册表 —— 收集所有插件，负责静态资源挂载、路由注册、页面注入、事件广播。

用法（在 main.py 装配阶段）：
    from app.plugins import get_registry
    registry = get_registry()
    registry.install(app, templates)   # 一次调用完成全部挂载

插件之间通过 registry.broadcast(plugin_id, payload) 广播事件，
各插件后端再把事件推给自己的 SSE 客户端（例如桌宠）。
"""
import asyncio
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from app.plugins.base import PluginBase


class CacheStaticFiles(StaticFiles):
    """带强缓存头的静态文件服务。

    用于体积大、内容不变的资源（如桌宠 WebM 动画、vendor JS）。
    Cache-Control: public, max-age=31536000, immutable（一年缓存）。
    """

    def file_response(self, *args, **kwargs) -> Response:
        resp = super().file_response(*args, **kwargs)
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp

logger = logging.getLogger(__name__)


class PluginRegistry:
    """插件注册表（进程内单例）。"""

    def __init__(self) -> None:
        self._plugins: Dict[str, PluginBase] = {}
        # 事件订阅：plugin_id -> 回调（用于 SSE 推送，插件后端自己注册）
        self._subscribers: Dict[str, List] = {}

    # ── 注册 / 查询 ─────────────────────────────────────────

    def register(self, plugin: PluginBase) -> None:
        if plugin.id in self._plugins:
            logger.warning("[plugins] 重复注册插件 %s，忽略", plugin.id)
            return
        self._plugins[plugin.id] = plugin
        logger.info("[plugins] 注册插件: %s (%s)", plugin.id, plugin.name)

    def get(self, plugin_id: str) -> Optional[PluginBase]:
        return self._plugins.get(plugin_id)

    def all(self) -> List[PluginBase]:
        return list(self._plugins.values())

    # ── 装配 ────────────────────────────────────────────────

    def install(self, app: FastAPI, templates=None) -> None:
        """把已注册插件的静态资源、路由、模板注入全部挂到 app 上。"""
        for plugin in self._plugins.values():
            self._mount_static(app, plugin)
            self._register_routes(app, plugin)

        if templates is not None:
            self._install_template_global(templates)
            logger.info("[plugins] 模板注入函数已安装 (plugin_scripts)")

    def _mount_static(self, app: FastAPI, plugin: PluginBase) -> None:
        static_dir = plugin.get_static_dir()
        if not static_dir or not static_dir.exists():
            logger.warning("[plugins] %s 静态资源目录不存在: %s", plugin.id, static_dir)
            return
        # 静态资源挂到 /plugins/{id}/assets 子路径，
        # 把 /plugins/{id}/config、/events、/say 等路由让出来（StaticFiles mount 会吞同前缀）。
        mount_path = f"/plugins/{plugin.id}/assets"
        app.mount(mount_path, CacheStaticFiles(directory=str(static_dir)), name=f"plugin-{plugin.id}")
        logger.info("[plugins] %s 静态资源已挂载: %s -> %s", plugin.id, mount_path, static_dir)

    def _register_routes(self, app: FastAPI, plugin: PluginBase) -> None:
        # 注意：静态资源挂在 /plugins/{id}，路由不能再用同一前缀
        # （FastAPI 的 StaticFiles mount 会吞掉同前缀的所有请求）。
        # 因此路由不加 prefix，由插件自己写完整路径（/plugins/{id}/config 等）。
        router = APIRouter(tags=[f"plugin:{plugin.id}"])
        plugin.register_routes(router)
        if len(router.routes) > 0:
            app.include_router(router)
            logger.info("[plugins] %s 路由已注册 (%d 条)", plugin.id, len(router.routes))

    def _install_template_global(self, templates) -> None:
        """往 Jinja2 模板注入 plugin_scripts(path) 全局函数。"""

        def plugin_scripts(path: str = "") -> str:
            tags = []
            for plugin in self._plugins.values():
                try:
                    if self._should_inject_by_path(plugin, path):
                        script = plugin.get_entry_script(None)  # 纯注入场景无 request
                        if script:
                            tags.append(script)
                except Exception as e:
                    logger.warning("[plugins] %s 注入脚本生成失败: %s", plugin.id, e)
            return "\n".join(tags)

        templates.env.globals["plugin_scripts"] = plugin_scripts

    @staticmethod
    def _should_inject_by_path(plugin: PluginBase, path: str) -> bool:
        """按路径判断是否注入。默认排除 /admin；其余交给插件自身决定。"""
        if path == "/admin" or path.startswith("/admin"):
            return False
        # 无 request 的纯路径判断：调用插件的默认逻辑
        # 这里用一个轻量判断——插件若自定义了 should_inject 逻辑，通过 subclass hook 处理
        return True

    # ── 事件广播（插件间 / 业务 → 插件）──────────────────────

    def subscribe(self, plugin_id: str, callback) -> None:
        """插件后端订阅事件：registry.subscribe('live2d-pet', my_broadcast_fn)。"""
        self._subscribers.setdefault(plugin_id, []).append(callback)

    def broadcast(self, plugin_id: str, payload: dict) -> None:
        """向某插件的所有订阅者广播事件（同步，线程安全）。

        chat_routes 在 AI 关键节点调用：
            registry.broadcast('live2d-pet', {'t': 'delta', 'text': chunk})
        """
        for cb in list(self._subscribers.get(plugin_id, [])):
            try:
                cb(payload)
            except Exception as e:
                logger.warning("[plugins] %s 广播失败: %s", plugin_id, e)

    def broadcast_async(self, plugin_id: str, payload: dict) -> None:
        """异步广播（在 async 上下文里使用，不阻塞事件循环）。"""
        for cb in list(self._subscribers.get(plugin_id, [])):
            try:
                result = cb(payload)
                if asyncio.iscoroutine(result):
                    # 回调是协程：交给当前事件循环
                    try:
                        asyncio.get_running_loop().create_task(result)
                    except RuntimeError:
                        pass
            except Exception as e:
                logger.warning("[plugins] %s 异步广播失败: %s", plugin_id, e)


# ── 单例 ──────────────────────────────────────────────────────

_registry: Optional[PluginRegistry] = None


def get_registry() -> PluginRegistry:
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
        _autoload(_registry)
    return _registry


def _autoload(registry: PluginRegistry) -> None:
    """自动加载内置插件。新增插件在此登记。"""
    from app.plugins.dsh_pet import DshPetPlugin
    registry.register(DshPetPlugin())
