"""
角色系统路由 —— 角色市场、导入、收藏、置顶、分享、绑定、人设参数开关。

路径：/ai/characters/*  /ai/character-settings
"""
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db, ChatSession
from app.core.db.models import User
from app.core.token_utils import get_optional_user_id, verify_token
from app.core import characters as charsvc

logger = logging.getLogger(__name__)
router = APIRouter()


# ── 请求模型 ────────────────────────────────────────────────

class CharacterSettings(BaseModel):
    active_message: Optional[bool] = None
    tone: Optional[str] = None            # light / normal / clingy
    meme_frequency: Optional[str] = None  # low / normal / high
    memory_sensitivity: Optional[str] = None  # low / high


class ImportCharacterReq(BaseModel):
    json_data: dict  # 角色包 JSON 内容


class SelectCharacterReq(BaseModel):
    character_id: str


class FavoriteReq(BaseModel):
    character_id: str
    favorite: bool = True


class PinReq(BaseModel):
    character_id: str
    pin: bool = True


# ── 工具函数 ────────────────────────────────────────────────

def _public_view(char: dict, prefs: dict) -> dict:
    """角色市场展示用：去掉完整 prompt，只留前端需要的信息 + 用户状态。"""
    return {
        "id": char.get("id"),
        "name": char.get("name"),
        "name_en": char.get("name_en"),
        "avatar": char.get("avatar"),
        "description": char.get("description"),
        "tags": char.get("tags", []),
        "builtin": char.get("builtin", False),
        "opening": char.get("opening", ""),
        "style": char.get("style", {}),
        "is_favorite": char.get("id") in (prefs.get("favorites") or []),
        "is_pinned": char.get("id") in (prefs.get("pinned") or []),
        "is_current": char.get("id") == (prefs.get("current_character") or charsvc.DEFAULT_CHARACTER_ID),
    }


# ── 角色市场 ────────────────────────────────────────────────

@router.get("/ai/characters")
def list_characters(user_id: Optional[int] = Depends(get_optional_user_id)):
    """列出所有角色（含收藏/置顶/当前状态）。"""
    prefs = charsvc.get_user_prefs(user_id)
    chars = charsvc.list_characters()
    result = [_public_view(c, prefs) for c in chars]
    # 排序：置顶优先，其次内置优先，最后按名称
    result.sort(key=lambda c: (
        not c["is_pinned"],
        not c["builtin"],
        c["name"],
    ))
    return {
        "characters": result,
        "current_character": prefs.get("current_character") or charsvc.DEFAULT_CHARACTER_ID,
        "settings": prefs.get("settings") or charsvc.DEFAULT_SETTINGS,
    }


@router.get("/ai/characters/{char_id}")
def get_character(char_id: str, user_id: Optional[int] = Depends(get_optional_user_id)):
    """获取单个角色详情（市场页展示，不含完整 prompt）。"""
    char = charsvc.load_character(char_id)
    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")
    prefs = charsvc.get_user_prefs(user_id)
    return _public_view(char, prefs)


# ── 导入角色 ────────────────────────────────────────────────

@router.post("/ai/characters/import")
def import_character(req: ImportCharacterReq, user_id: Optional[int] = Depends(get_optional_user_id)):
    """导入自定义角色包（JSON）。未登录只返回预览，不落盘。"""
    data = req.json_data or {}
    if not data.get("id") or not data.get("name") or not data.get("persona"):
        raise HTTPException(status_code=400, detail="角色包缺少必填字段：id / name / persona")
    # 校验 id 安全
    safe_id = "".join(c for c in data["id"] if c.isalnum() or c in "-_")
    if safe_id != data["id"]:
        raise HTTPException(status_code=400, detail="角色 id 只能包含字母、数字、-、_")

    # 内置角色 id 冲突拒绝覆盖
    if safe_id in {"maid", "senpai", "cool", "heal", "brat"}:
        raise HTTPException(status_code=400, detail="不能覆盖内置角色，请换一个 id")

    if not user_id:
        # 未登录：仅返回规范化后的预览
        return {"preview": True, "character": data}

    # 落盘到角色目录（用户导入角色保存在 plugins/characters/ 下）
    charsvc.CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
    path = charsvc.CHARACTERS_DIR / f"{safe_id}.json"
    data["id"] = safe_id
    data["builtin"] = False
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"preview": False, "character": data}


# ── 收藏 / 置顶 ─────────────────────────────────────────────

@router.post("/ai/characters/favorite")
def toggle_favorite(req: FavoriteReq, user_id: Optional[int] = Depends(get_optional_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    prefs = charsvc.get_user_prefs(user_id)
    favs = set(prefs.get("favorites") or [])
    if req.favorite:
        favs.add(req.character_id)
    else:
        favs.discard(req.character_id)
    prefs["favorites"] = sorted(favs)
    charsvc.save_user_prefs(user_id, {"favorites": prefs["favorites"]})
    return {"favorites": prefs["favorites"]}


@router.post("/ai/characters/pin")
def toggle_pin(req: PinReq, user_id: Optional[int] = Depends(get_optional_user_id)):
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    prefs = charsvc.get_user_prefs(user_id)
    pins = set(prefs.get("pinned") or [])
    if req.pin:
        pins.add(req.character_id)
    else:
        pins.discard(req.character_id)
    prefs["pinned"] = sorted(pins)
    charsvc.save_user_prefs(user_id, {"pinned": prefs["pinned"]})
    return {"pinned": prefs["pinned"]}


# ── 分享链接 ────────────────────────────────────────────────

@router.get("/ai/characters/{char_id}/share")
def share_character(char_id: str, request: Request):
    """生成角色分享链接（返回可直接访问的链接，前端拼 URL）。"""
    char = charsvc.load_character(char_id)
    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")
    base = str(request.base_url).rstrip("/")
    return {
        "url": f"{base}/chat?character={char_id}",
        "character_id": char_id,
        "name": char.get("name"),
    }


# ── 绑定角色到主对话 ────────────────────────────────────────

@router.post("/ai/characters/select")
def select_character(req: SelectCharacterReq, user_id: Optional[int] = Depends(get_optional_user_id), db: Session = Depends(get_db)):
    """绑定角色到用户主对话（一个主对话固定一个人格）。

    换角色时：更新 User.character_prefs.current_character + 主对话 ChatSession.character_id。
    前端据此重新渲染主对话（重新拉历史时用新角色）。
    """
    char = charsvc.load_character(req.character_id)
    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")

    if user_id:
        prefs = charsvc.get_user_prefs(user_id)
        prefs["current_character"] = req.character_id
        charsvc.save_user_prefs(user_id, {"current_character": req.character_id})

        # 更新主对话会话的角色绑定，并清空旧角色历史（换角色=主对话重新开始，
        # 避免旧人格的话与新人格混在一起导致「人格乱跳」）
        main_session = (
            db.query(ChatSession)
            .filter(ChatSession.user_id == user_id, ChatSession.chat_type == "main")
            .order_by(ChatSession.id.asc())
            .first()
        )
        if main_session:
            from app.core.db import Message
            main_session.character_id = req.character_id
            # 清空该主对话下的所有历史消息（旧人格对话作废）
            db.query(Message).filter(Message.session_id == main_session.id).delete()
            db.commit()

    return {
        "character_id": req.character_id,
        "name": char.get("name"),
        "opening": char.get("opening", ""),
    }


# ── 人设参数开关 ────────────────────────────────────────────

@router.get("/ai/character-settings")
def get_settings(user_id: Optional[int] = Depends(get_optional_user_id)):
    """读取人设参数开关（侧边小设置面板）。"""
    settings = charsvc.get_user_settings(user_id)
    return {"settings": settings}


@router.post("/ai/character-settings")
def save_settings(req: CharacterSettings, user_id: Optional[int] = Depends(get_optional_user_id)):
    """保存人设参数开关。"""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    updates = {k: v for k, v in req.dict().items() if v is not None}
    # 校验枚举值
    if "tone" in updates and updates["tone"] not in ("light", "normal", "clingy"):
        raise HTTPException(status_code=400, detail="tone 取值：light/normal/clingy")
    if "meme_frequency" in updates and updates["meme_frequency"] not in ("low", "normal", "high"):
        raise HTTPException(status_code=400, detail="meme_frequency 取值：low/normal/high")
    if "memory_sensitivity" in updates and updates["memory_sensitivity"] not in ("low", "high"):
        raise HTTPException(status_code=400, detail="memory_sensitivity 取值：low/high")
    settings = charsvc.save_user_settings(user_id, updates)
    return {"settings": settings}
