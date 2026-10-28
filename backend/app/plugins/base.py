"""
网页插件接口 —— 插件系统的抽象基类。

一个「插件」= 前端静态资源 + 后端路由 + 页面注入规则。
任何虚拟形象 / 挂件 / 增强功能，只要实现本接口并注册到 registry，
就能自动挂载静态资源、注入页面脚本、暴露专属路由。

设计目标：
  - 暴露最小、稳定的接口（id / name / 三个方法）
  - 页面注入按请求路径精确控制（例如 /admin 不注入）
  - 静态资源统一挂在 /plugins/{id}/ 下
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request


class PluginBase(ABC):
    """网页插件抽象基类。"""

    # ── 元信息 ──────────────────────────────────────────────

    @property
    @abstractmethod
    def id(self) -> str:
        """插件唯一标识（如 "live2d-pet"），同时是静态资源 URL 前缀。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """插件显示名。"""

    # ── 静态资源 ────────────────────────────────────────────

    @abstractmethod
    def get_static_dir(self) -> Path:
        """前端资源目录，会被挂载到 /plugins/{id}/。"""

    # ── 页面注入 ────────────────────────────────────────────

    def should_inject(self, request: Request) -> bool:
        """是否在该请求对应的页面上注入脚本。

        默认对所有 GET 页面注入；子类可覆盖以排除特定路径（如 /admin）。
        """
        return request.method in ("GET", "HEAD")

    def get_entry_script(self, request: Request) -> Optional[str]:
        """要注入页面的 <script> 标签 HTML；返回 None/空串则不注入。"""
        raise NotImplementedError

    # ── 后端路由 ────────────────────────────────────────────

    @abstractmethod
    def register_routes(self, router: APIRouter) -> None:
        """插件专属后端路由（SSE 事件流、配置、反向通道等）。"""
