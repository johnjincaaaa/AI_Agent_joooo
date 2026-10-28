"""
dsh-pet 桌宠插件 —— 轻量 WebM 播放器版。

从 dsh-pet（DSH 插件，TS+React）拆出的简化版：
  - 前端资产：透明 WebM 动画（106 个）+ config.jsonc + pet.js（原生 JS 播放器）
  - 后端：静态资源挂载 + /config + /events（SSE 事件流）

事件联动（P2）：
  chat_routes 在 AI 关键节点调用 registry.broadcast('dsh-pet', {...})，
  本插件订阅这些事件，通过 SSE 推给前端桌宠，
  桌宠按状态切换「工作状态」动画（思考/忙碌/整理/等待/庆祝/出错）。
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.paths import project_root
from app.plugins.base import PluginBase
from app.plugins import get_registry

logger = logging.getLogger(__name__)


class DshPetPlugin(PluginBase):
    """dsh-pet 桌宠插件（轻量 WebM 播放器）。"""

    def __init__(self) -> None:
        # SSE 客户端：每个连接一个 asyncio.Queue
        self._queues: set = set()
        # 订阅 registry 事件，chat_routes 广播时推给前端
        get_registry().subscribe(self.id, self._on_event)

    @property
    def id(self) -> str:
        return "dsh-pet"

    @property
    def name(self) -> str:
        return "蓝毛小女仆桌宠"

    def get_static_dir(self) -> Path:
        # 前端资源：front/static/plugins/dsh-pet/assets/
        return project_root() / "front" / "static" / "plugins" / "dsh-pet" / "assets"

    def get_entry_script(self, request: Optional[Request] = None) -> str:
        """注入 <script>：先写全局配置，再加载桌宠脚本。"""
        base = f"/plugins/{self.id}"
        asset_base = f"{base}/assets"
        return (
            "<script>"
            "window.__DSH_PET_BOOT__ = window.__DSH_PET_BOOT__ || {};"
            f"window.__DSH_PET_BOOT__.base = '{base}';"
            f"window.__DSH_PET_BOOT__.assetBase = '{asset_base}';"
            "</script>"
            f'<script defer src="{asset_base}/pet.js"></script>'
        )

    # ── 事件订阅（chat_routes 广播 → 推给 SSE 客户端）──────────

    def _on_event(self, payload: dict) -> None:
        """registry.broadcast('dsh-pet', payload) 的回调。

        把事件投递到所有已连接的 SSE 客户端队列。
        （回调可能在 async 或 sync 上下文被调，用线程安全的 try/except 投递。）
        """
        for q in list(self._queues):
            try:
                # put_nowait 线程安全，SSE 生成器会从队列取出
                q.put_nowait(payload)
            except Exception:
                pass

    def register_routes(self, router: APIRouter) -> None:
        """插件专属路由：/config、/events（SSE）、/say（反向通道）。"""
        base = f"/plugins/{self.id}"

        @router.get(f"{base}/config")
        async def pet_config():
            return {
                "enabled": True,
                "size": 280,
                "corner": "top-right",
                "workStatusEnabled": True,
            }

        @router.post(f"{base}/say")
        async def pet_say(request: Request):
            """反向通道：桌宠输入 → 主 AI 对话（深绑定）。

            复用 chat_routes.run_chat_turn，走与主 chat 完全相同的流程：
            同一人设（蓝发小女仆）+ 同一记忆 + 同一会话历史。
            桌宠前端在气泡里显示回复。
            """
            from app.api.chat_routes import run_chat_turn, ChatMessage
            from app.core.db import SessionLocal
            from app.core.token_utils import get_optional_user_id, oauth2_scheme_optional
            from fastapi import Depends

            try:
                body = await request.json()
            except Exception:
                return {"ok": False, "error": "invalid json"}

            text = (body.get("text") or "").strip()
            if not text:
                return {"ok": False, "error": "empty text"}

            # 解析当前登录用户（从 Authorization header / cookie）
            from app.core.token_utils import _decode_token_or_none
            auth_header = request.headers.get("authorization", "")
            token = None
            if auth_header.lower().startswith("bearer "):
                token = auth_header[7:]
            else:
                for key in ("jingent_token", "auth_token", "jingent_session"):
                    token = request.cookies.get(key)
                    if token:
                        break
            user_id = _decode_token_or_none(token)

            # 会话历史（前端传当前 chatData，缺省空）
            history_raw = body.get("history") or []
            history = [
                ChatMessage(role=m.get("role", "user"), message=m.get("message", ""), reactions=m.get("reactions", {}))
                for m in history_raw
                if isinstance(m, dict) and m.get("message")
            ]

            try:
                # 复用主 chat 的对话核心（人设 + 记忆 + 历史 + LLM）
                db = SessionLocal()
                try:
                    ai_reply, new_history, llm_info = run_chat_turn(
                        history=history,
                        new_message=text,
                        user_id=user_id,
                        db=db,
                        llm_config=body.get("llm"),
                        scene=body.get("scene"),
                        lang=body.get("lang") or "zh",
                        enabled_skills=body.get("enabled_skills"),
                        temperature=float(body.get("temperature") or 0.7),
                        open_online=bool(body.get("open_online")),
                        chat_type="main",  # 桌宠对话永远属于主对话（陪伴入口）
                        character_id=body.get("character_id"),  # 角色包 ID（缺省用用户绑定角色）
                    )
                finally:
                    db.close()

                # 广播给桌宠前端：显示回复气泡
                self._on_event({"t": "say-reply", "text": ai_reply})
                # 也广播 turn 事件，让桌宠动画联动
                self._on_event({"t": "turn-end", "status": "success"})
                return {"ok": True, "reply": ai_reply}
            except Exception as e:
                logger.warning("[dsh-pet] /say 调用失败: %s", e)
                return {"ok": False, "error": str(e)[:200]}

        @router.get(f"{base}/events")
        async def pet_events(request: Request):
            """SSE 事件流：AI 状态 → 桌宠工作状态动画。"""
            q: asyncio.Queue = asyncio.Queue()
            self._queues.add(q)

            async def stream():
                try:
                    # 首帧 hello
                    yield "data: " + json.dumps({"t": "hello", "status": "idle"}) + "\n\n"
                    while True:
                        try:
                            # 15 秒超时 → 发心跳
                            payload = await asyncio.wait_for(q.get(), timeout=15)
                            yield "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"
                        except asyncio.TimeoutError:
                            yield ": ping\n\n"
                finally:
                    self._queues.discard(q)

            return StreamingResponse(stream(), media_type="text/event-stream")
