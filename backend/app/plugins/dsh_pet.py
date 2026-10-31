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
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.paths import project_root
from app.plugins.base import PluginBase
from app.plugins import get_registry

logger = logging.getLogger(__name__)

# pet.js 版本号（每次启动变化，用于破坏浏览器缓存）
PET_ASSET_VERSION = str(int(time.time()))


async def _resolve_user_id(request: Request) -> Optional[int]:
    """手动解析登录用户（避免直接依赖 get_optional_user_id 的 Depends 注入）。"""
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
    return _decode_token_or_none(token)


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
            f'<script defer src="{asset_base}/pet.js?v={PET_ASSET_VERSION}"></script>'
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
        """插件专属路由：/config、/events（SSE）、/say（反向通道）、用户资源上传/配置。"""
        base = f"/plugins/{self.id}"

        @router.get(f"{base}/config")
        async def pet_config(request: Request):
            """合并配置：内置默认 + 用户上传资源与触发条件（pet.js 启动时拉取）。"""
            from app.core.pet_assets import merged_config
            
            user_id = await _resolve_user_id(request)
            return {
                "enabled": True,
                "size": 280,
                "corner": "top-right",
                "workStatusEnabled": True,
                **merged_config(user_id),
            }

        @router.post(f"{base}/upload")
        async def pet_upload(request: Request):
            """上传宠物资源：动画(.webm) / 表情包(.png等) / 音效(.webm/.wav等)。"""
            from app.core.pet_assets import save_upload
            

            user_id = await _resolve_user_id(request)
            if user_id is None:
                return {"ok": False, "error": "请先登录"}

            content_type = request.headers.get("content-type", "")
            if "multipart/form-data" not in content_type:
                # 兜底：原始字节 + query 参数
                try:
                    raw = await request.body()
                except Exception:
                    raw = b""
                kind = request.query_params.get("kind", "")
                filename = request.query_params.get("filename", "")
                if not raw or not kind or not filename:
                    return {"ok": False, "error": "需要 multipart 或 kind/filename 参数"}
                return save_upload(user_id, kind, filename, raw)

            try:
                form = await request.form()
            except Exception as e:
                return {"ok": False, "error": f"解析表单失败: {str(e)[:100]}"}

            kind = str(form.get("kind") or request.query_params.get("kind") or "").strip()
            upload = form.get("file")
            if upload is None or not hasattr(upload, "filename"):
                return {"ok": False, "error": "缺少 file 字段"}
            filename = upload.filename or "unnamed"
            content = await upload.read()
            return save_upload(user_id, kind, filename, content)

        @router.get(f"{base}/user-config")
        async def pet_get_user_config(request: Request):
            from app.core.pet_assets import load_user_config, merged_config
            
            user_id = await _resolve_user_id(request)
            if user_id is None:
                return {"ok": False, "error": "请先登录"}
            return {"ok": True, "config": load_user_config(user_id), "merged": merged_config(user_id)}

        @router.post(f"{base}/user-config")
        async def pet_save_user_config(request: Request):
            from app.core.pet_assets import save_user_config, merged_config
            
            user_id = await _resolve_user_id(request)
            if user_id is None:
                return {"ok": False, "error": "请先登录"}
            try:
                body = await request.json()
            except Exception:
                return {"ok": False, "error": "invalid json"}
            clean = save_user_config(user_id, body)
            return {"ok": True, "config": clean, "merged": merged_config(user_id)}

        @router.delete(f"{base}/resource")
        async def pet_delete_resource(request: Request):
            from app.core.pet_assets import delete_resource
            
            user_id = await _resolve_user_id(request)
            if user_id is None:
                return {"ok": False, "error": "请先登录"}
            kind = request.query_params.get("kind", "")
            name = request.query_params.get("name", "")
            return delete_resource(user_id, kind, name)

        @router.post(f"{base}/say")
        async def pet_say(request: Request):
            """反向通道：桌宠输入 → 主 AI 对话（深绑定）。

            复用 chat_routes.run_chat_turn，走与主 chat 完全相同的流程：
            同一人设（蓝发小女仆）+ 同一记忆 + 同一会话历史。
            桌宠前端在气泡里显示回复。
            """
            from app.api.chat_routes import run_chat_turn, ChatMessage
            from app.core.db import SessionLocal

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

                    # ── 入库：桌宠 /say 的消息必须写进主对话历史 ──
                    # 主 chat 走 chatStream + savaToDb 入库，/say 不走那条链路，
                    # 需要在这里直接把「用户消息 + AI 回复」写入 Message 表与 session.messages，
                    # 否则桌宠主动发的信息不会进入上下文历史/记忆，切换灵魂后也无法正确隔离。
                    if user_id:
                        try:
                            from app.core.db import ChatSession, Message
                            from datetime import datetime, timezone as _tz

                            session = (
                                db.query(ChatSession)
                                .filter(ChatSession.user_id == user_id, ChatSession.chat_type == "main")
                                .order_by(ChatSession.id.asc())
                                .first()
                            )
                            if session is None:
                                session = ChatSession(
                                    user_id=user_id,
                                    session_name="主对话",
                                    session_time=0,
                                    messages=[],
                                    chat_type="main",
                                )
                                db.add(session)
                                db.flush()

                            # 解析当前灵魂（与 run_chat_turn 一致：前端传的角色优先，缺省用户绑定）
                            cid = body.get("character_id")
                            if not cid:
                                try:
                                    from app.core import characters as charsvc
                                    cid = charsvc.get_current_character_id(user_id)
                                except Exception:
                                    cid = None
                            if cid:
                                session.character_id = cid

                            # 用户消息 + AI 回复（new_history 已含用户消息与拆分后的 AI 回复）
                            from app.api.chat_routes import _parse_dt
                            now = datetime.now(_tz.utc)
                            json_rows = []
                            for m in new_history:
                                role = m.role if m.role in ("user", "ai") else "user"
                                content = (m.message or "").strip()
                                if not content:
                                    continue
                                # created_at 是 ISO 字符串，转成 datetime 再存 DateTime 列
                                created = _parse_dt(m.created_at) or now
                                db.add(Message(
                                    session_id=session.id,
                                    user_id=user_id,
                                    role=role,
                                    content=content,
                                    reactions=m.reactions or {},
                                    created_at=created,
                                    character_id=cid,
                                ))
                                json_rows.append({
                                    "role": role,
                                    "message": content,
                                    "reactions": m.reactions or {},
                                })
                            # 兼容字段：同步 session.messages（旧 JSON 读取路径）
                            session.messages = json_rows
                            db.commit()

                            # 后台抽取记忆（不阻塞响应，按角色隔离）
                            try:
                                from app.api.chat_routes import _schedule_memory_extract
                                # llm_info = (model_name, base_url, api_key)
                                _schedule_memory_extract(
                                    user_id, text, ai_reply,
                                    llm_info[1], llm_info[0], llm_info[2],
                                    character_id=cid,
                                )
                            except Exception:
                                pass
                        except Exception as e:
                            logger.warning("[dsh-pet] /say 入库失败: %s", e)
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
