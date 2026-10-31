"""
Jingent 创作中心路由 —— /chat/create 列表页 + /chat/create/edit 编辑页的后端 API。

路径：/ai/create/*
功能：
  - 用户创建自定义角色（独立记忆体创建 + 宠物模型）
  - 草稿 / 审核中 / 已发布 三态管理
  - 「使用」：把自定义角色导入到对话（落盘到角色目录 + 绑定当前角色）
"""
import json
import logging
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db, SessionLocal, ChatSession
from app.core.db.models import CustomCharacter, User
from app.core.token_utils import get_optional_user_id
from app.core import characters as charsvc

logger = logging.getLogger(__name__)
router = APIRouter()


# ── 请求模型 ────────────────────────────────────────────────

class SaveCharacterReq(BaseModel):
    npc_id: Optional[str] = None        # 传则更新，不传则新建（生成时间戳）
    name: str
    description: Optional[str] = ""
    persona: Optional[str] = ""
    opening: Optional[str] = ""
    rules: Optional[List[str]] = []
    style: Optional[dict] = {}
    avatar: Optional[str] = ""
    appearance: Optional[str] = ""
    tags: Optional[List[str]] = []
    voice: Optional[str] = None          # 绑定音色（VoiceStudio 音色 ID/名字）


class SubmitReq(BaseModel):
    npc_id: str


# ── 工具函数 ────────────────────────────────────────────────

STATUS_LABELS = {
    "draft": "草稿",
    "pending": "审核中",
    "approved": "已发布",
    "rejected": "未通过",
}


def _serialize(cc: CustomCharacter) -> dict:
    """把 ORM 对象转成前端需要的字典。"""
    return {
        "npc_id": cc.npc_id,
        "name": cc.name,
        "description": cc.description or "",
        "persona": cc.persona or "",
        "opening": cc.opening or "",
        "rules": cc.rules or [],
        "style": cc.style or {},
        "avatar": cc.avatar or "",
        "appearance": cc.appearance or "",
        "tags": cc.tags or [],
        "voice": cc.voice or "",
        "status": cc.status,
        "status_label": STATUS_LABELS.get(cc.status, cc.status),
        "created_at": cc.created_at.isoformat() if cc.created_at else None,
        "updated_at": cc.updated_at.isoformat() if cc.updated_at else None,
    }


def _card_view(cc: CustomCharacter) -> dict:
    """列表卡片视图（不含完整 prompt，减少体积）。"""
    return {
        "npc_id": cc.npc_id,
        "name": cc.name,
        "description": cc.description or "",
        "avatar": cc.avatar or "",
        "voice": cc.voice or "",
        "status": cc.status,
        "status_label": STATUS_LABELS.get(cc.status, cc.status),
        "updated_at": cc.updated_at.isoformat() if cc.updated_at else None,
    }


# ── 页面路由（由 chat_routes 或 main 注册，这里只做 API）─────

@router.get("/ai/create/characters")
def list_created_characters(
    status: Optional[str] = None,
    user_id: Optional[int] = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
):
    """列出当前用户创建的角色。status: all/draft/pending/approved，缺省 all。"""
    if not user_id:
        return {"ok": True, "characters": [], "logged_in": False}
    q = db.query(CustomCharacter).filter(CustomCharacter.user_id == user_id)
    if status and status in ("draft", "pending", "approved"):
        q = q.filter(CustomCharacter.status == status)
    rows = q.order_by(CustomCharacter.updated_at.desc()).all()
    return {"ok": True, "characters": [_card_view(r) for r in rows], "logged_in": True}


@router.get("/ai/create/characters/{npc_id}")
def get_created_character(
    npc_id: str,
    user_id: Optional[int] = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
):
    """获取单个自定义角色详情（编辑器回显）。"""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    cc = db.query(CustomCharacter).filter(
        CustomCharacter.npc_id == npc_id,
        CustomCharacter.user_id == user_id,
    ).first()
    if not cc:
        raise HTTPException(status_code=404, detail="角色不存在")
    return {"ok": True, "character": _serialize(cc)}


@router.get("/ai/create/characters/{npc_id}/import")
def import_created_character(
    npc_id: str,
    user_id: Optional[int] = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
):
    """通过分享链接导入他人记忆体：仅允许读取「已通过审核」的角色公开信息。"""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    cc = db.query(CustomCharacter).filter(CustomCharacter.npc_id == npc_id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="角色不存在")
    if cc.status != "approved":
        raise HTTPException(status_code=400, detail="该记忆体尚未通过审核，无法导入")
    # 分享出去的是只读预览；导入时去掉归属信息，前端会作为新草稿保存
    return {"ok": True, "character": _serialize(cc), "shared": True}


@router.post("/ai/create/characters")
def save_created_character(
    req: SaveCharacterReq,
    user_id: Optional[int] = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
):
    """保存草稿：新建（生成 npc_id=毫秒时间戳）或更新已有草稿。"""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    if not (req.name or "").strip():
        raise HTTPException(status_code=400, detail="角色名称不能为空")

    now = time.time() * 1000
    if req.npc_id:
        # 更新已有角色（仅限本人、且仅草稿可编辑）
        cc = db.query(CustomCharacter).filter(
            CustomCharacter.npc_id == req.npc_id,
            CustomCharacter.user_id == user_id,
        ).first()
        if not cc:
            raise HTTPException(status_code=404, detail="角色不存在")
        if cc.status not in ("draft",):
            raise HTTPException(status_code=400, detail="只有草稿状态可编辑")
    else:
        # 新建：生成 npc_id（毫秒时间戳，保证唯一）
        npc_id = str(int(now))
        # 极端情况撞时间戳：往上加一，直到唯一
        while db.query(CustomCharacter).filter(CustomCharacter.npc_id == npc_id).first():
            now += 1
            npc_id = str(int(now))
        cc = CustomCharacter(
            npc_id=npc_id,
            user_id=user_id,
            name="",
            status="draft",
        )
        db.add(cc)

    cc.name = (req.name or "").strip()
    cc.description = (req.description or "").strip()
    cc.persona = (req.persona or "").strip()
    cc.opening = (req.opening or "").strip()
    cc.rules = req.rules or []
    cc.style = req.style or {}
    cc.avatar = (req.avatar or "").strip()
    cc.appearance = (req.appearance or "").strip()
    cc.tags = req.tags or []
    cc.voice = (req.voice or "").strip()
    # 保存后仍是草稿（不会直接上架）
    cc.status = "draft"
    db.commit()
    db.refresh(cc)
    return {"ok": True, "character": _serialize(cc)}


@router.delete("/ai/create/characters/{npc_id}")
def delete_created_character(
    npc_id: str,
    user_id: Optional[int] = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
):
    """删除自定义角色（仅本人）。"""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    cc = db.query(CustomCharacter).filter(
        CustomCharacter.npc_id == npc_id,
        CustomCharacter.user_id == user_id,
    ).first()
    if not cc:
        raise HTTPException(status_code=404, detail="角色不存在")
    db.delete(cc)
    db.commit()
    return {"ok": True, "npc_id": npc_id}


@router.post("/ai/create/characters/{npc_id}/submit")
def submit_created_character(
    npc_id: str,
    user_id: Optional[int] = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
):
    """提交审核：draft → pending。"""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    cc = db.query(CustomCharacter).filter(
        CustomCharacter.npc_id == npc_id,
        CustomCharacter.user_id == user_id,
    ).first()
    if not cc:
        raise HTTPException(status_code=404, detail="角色不存在")
    if cc.status != "draft":
        raise HTTPException(status_code=400, detail="只有草稿状态可提交审核")
    if not (cc.name or "").strip() or not (cc.persona or "").strip():
        raise HTTPException(status_code=400, detail="角色名称和人设不能为空")
    cc.status = "pending"
    db.commit()
    db.refresh(cc)
    return {"ok": True, "character": _serialize(cc)}


@router.post("/ai/create/characters/{npc_id}/use")
def use_created_character(
    npc_id: str,
    user_id: Optional[int] = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
):
    """使用自定义角色：导入到对话（落盘为角色包 + 绑定当前角色）。"""
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    cc = db.query(CustomCharacter).filter(
        CustomCharacter.npc_id == npc_id,
        CustomCharacter.user_id == user_id,
    ).first()
    if not cc:
        raise HTTPException(status_code=404, detail="角色不存在")
    # 只有审核通过（approved）的角色才能使用；草稿/审核中/拒绝均禁止导入对话
    if cc.status != "approved":
        status_hint = {"draft": "草稿", "pending": "审核中", "rejected": "未通过"}.get(cc.status, cc.status)
        raise HTTPException(status_code=400, detail=f"该记忆体当前为「{status_hint}」状态，审核通过后才能使用")

    # 组装成角色包 JSON（与内置角色同构，builtin=False）
    char_id = f"npc_{cc.npc_id}"
    package = {
        "id": char_id,
        "name": cc.name,
        "description": cc.description or "",
        "tags": cc.tags or [],
        "builtin": False,
        "persona": cc.persona or "",
        "rules": cc.rules or [],
        "style": cc.style or {},
        "avatar": cc.avatar or "",
        "opening": cc.opening or "",
        "voice": cc.voice or "",
    }

    # 落盘到角色目录（用户自定义角色，与内置角色同目录，builtin=False 区分）
    charsvc.CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
    path = charsvc.CHARACTERS_DIR / f"{char_id}.json"
    path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")

    # 绑定为当前角色
    charsvc.save_user_prefs(user_id, {"current_character": char_id})
    main_session = (
        db.query(ChatSession).filter(
            ChatSession.user_id == user_id, ChatSession.chat_type == "main"
        ).order_by(ChatSession.id.asc()).first()
    )
    if main_session:
        main_session.character_id = char_id
        db.commit()

    return {
        "ok": True,
        "character_id": char_id,
        "name": cc.name,
        "opening": cc.opening or "",
    }
