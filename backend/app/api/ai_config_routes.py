"""
AI 配置路由 —— 用户级 AI 能力配置（跟随登录用户，数据库持久化，云端覆盖 .env）。

配置优先级（全局约定）：
    .env（服务器默认）  <  用户数据库配置（前端系统设置里填写）

配置 JSON 结构（user_ai_configs.config）：
    {
      "llm":        {"base_url", "model", "api_key"},          # 对话文本模型
      "embedding":  {"base_url", "model", "api_key"},          # 向量模型
      "image_vl":   {"provider", "base_url", "model", "api_key"},  # 图片解析模型（dashscope/glm/ollama）
      "voice": {
          "provider": "voicestudio|doubao|cosyvoice|glm",      # 语音厂商（互斥单选）
          "model": "", "api_key": "",
          "app_id": "", "access_token": "",                    # 豆包等需额外凭据
          "voice_id": "",                                      # 默认音色 ID
          "cloned_voices": []                                  # 三方克隆音色 [{voice_id,name}]
      }
    }

本模块只负责配置读写与合并；真正的调用由 chat_routes / tts_routes / 语音适配层消费。
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db, UserAIConfig
from app.core.token_utils import verify_token

logger = logging.getLogger(__name__)
router = APIRouter()


# ── 请求模型 ────────────────────────────────────────────────

class AIConfigBody(BaseModel):
    config: dict = {}


# ── 工具 ───────────────────────────────────────────────────

def _empty_cfg() -> dict:
    return {
        "llm": {"base_url": "", "model": "", "api_key": ""},
        "embedding": {"base_url": "", "model": "", "api_key": ""},
        "image_vl": {"provider": "", "base_url": "", "model": "", "api_key": ""},
        "voice": {
            "provider": "",
            "model": "",
            "api_key": "",
            "app_id": "",
            "access_token": "",
            "voice_id": "",
            "cloned_voices": [],
        },
    }


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并两个配置 dict；override 覆盖 base，保持结构完整。"""
    out = {}
    for k, v in (base or {}).items():
        out[k] = v
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def get_user_ai_config(db: Session, user_id: int) -> dict:
    """读用户 AI 配置；无记录返回空结构（不落库）。"""
    row = db.query(UserAIConfig).filter(UserAIConfig.user_id == user_id).first()
    if not row:
        return _empty_cfg()
    return _deep_merge(_empty_cfg(), row.config or {})


def save_user_ai_config(db: Session, user_id: int, config: dict) -> dict:
    """保存用户 AI 配置（深合并进现有配置，避免整表覆盖丢字段）。"""
    row = db.query(UserAIConfig).filter(UserAIConfig.user_id == user_id).first()
    merged = _deep_merge(get_user_ai_config(db, user_id), config or {})
    if not row:
        row = UserAIConfig(user_id=user_id, config=merged)
        db.add(row)
    else:
        row.config = merged
        row.updated_at = datetime.now()
    db.commit()
    return merged


# ── 路由 ───────────────────────────────────────────────────

@router.get("/ai/config", summary="读取当前用户 AI 配置（用户覆盖值，留空回退 .env）")
def read_ai_config(
    user_id: int = Depends(verify_token),
    db: Session = Depends(get_db),
):
    return {"ok": True, "config": get_user_ai_config(db, user_id)}


@router.put("/ai/config", summary="保存当前用户 AI 配置（深合并，跟随登录用户）")
def write_ai_config(
    body: AIConfigBody,
    user_id: int = Depends(verify_token),
    db: Session = Depends(get_db),
):
    merged = save_user_ai_config(db, user_id, body.config or {})
    return {"ok": True, "config": merged}


# ── 测试接口 ───────────────────────────────────────────────

class EmbeddingTestReq(BaseModel):
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    text: str = "测试向量化"


@router.post("/ai/config/test/embedding", summary="测试向量模型连通性（返回向量维度）")
def test_embedding_config(body: EmbeddingTestReq):
    from app.core.rag import _embed_texts
    try:
        emb = _embed_texts(
            [(body.text or "测试向量化").strip()],
            embedding_cfg={
                "base_url": body.base_url or None,
                "model": body.model or None,
                "api_key": body.api_key or None,
            },
        )[0]
        dim = len(emb or [])
        if dim <= 0:
            raise HTTPException(status_code=502, detail="向量模型返回空向量")
        return {"code": 200, "msg": "向量化成功", "dim": dim}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("[ai/config] 向量测试失败: %s", e)
        raise HTTPException(status_code=502, detail=f"向量测试失败：{str(e)[:200]}")


@router.post("/ai/config/test/image", summary="测试图片解析模型（上传图片识别）")
async def test_image_config(
    file: UploadFile = File(...),
    provider: str = Form(""),
    base_url: str = Form(""),
    model: str = Form(""),
    api_key: str = Form(""),
):
    """上传一张图片，按给定 provider 配置走识别通道，返回识别结果。"""
    import tempfile
    import os as _os
    from app.tools import tool_Image_parsing as image_tool

    audio_like = (file.filename or "img.jpg").lower()
    if not any(audio_like.endswith(e) for e in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")):
        raise HTTPException(status_code=400, detail="仅支持图片格式（jpg/png/webp/gif/bmp）")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="图片内容为空")

    # 写入临时文件，复用 image_analyze 的 PIL 读取逻辑
    suffix = "." + audio_like.rsplit(".", 1)[-1]
    fd, tmp = tempfile.mkstemp(suffix=suffix)
    try:
        with _os.fdopen(fd, "wb") as f:
            f.write(data)
        # 注入测试配置（用户填写的 provider/model/key）
        image_tool.set_user_image_vl_config({
            "provider": (provider or "").strip() or "ollama",
            "base_url": (base_url or "").strip(),
            "model": (model or "").strip(),
            "api_key": (api_key or "").strip(),
        })
        try:
            result = image_tool.image_analyze.func(tmp) if hasattr(image_tool.image_analyze, "func") else image_tool.image_analyze(tmp)
        finally:
            image_tool.set_user_image_vl_config(None)
        return {"code": 200, "msg": "识别成功", "result": result}
    finally:
        try:
            _os.unlink(tmp)
        except Exception:
            pass
