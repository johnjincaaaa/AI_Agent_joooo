"""
DSH 宠物插件市场路由 —— git 导入 / AI 安装 / 列表 / 切换 / 卸载。

路径：/ai/pet-market/*
"""
import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.token_utils import get_optional_user_id
from app.core import pet_market, pet_assets

logger = logging.getLogger(__name__)
router = APIRouter()


# ── 请求模型 ────────────────────────────────────────────────

class InstallReq(BaseModel):
    git_url: str
    pet_id: Optional[str] = None
    use_ai: bool = False   # True 时用 AI 辅助识别仓库结构


class SwitchReq(BaseModel):
    pet_id: Optional[str] = None   # None = 切回默认（大肥鱼）


# ── 工具 ────────────────────────────────────────────────────

def _require_user(user_id: Optional[int]) -> int:
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    return user_id


def _tree(repo: Path, max_depth: int = 3) -> str:
    """生成仓库文件树摘要（供 AI 分析）。"""
    lines = []
    for p in sorted(repo.rglob("*")):
        if ".git" in p.parts:
            continue
        rel = p.relative_to(repo)
        if len(rel.parts) > max_depth:
            continue
        if p.is_dir():
            lines.append(str(rel) + "/")
        else:
            lines.append(str(rel))
    return "\n".join(lines[:300])


def _ai_analyze(git_url: str, tree: str) -> dict:
    """用项目 LLM 分析仓库结构，返回 {config_path, webm_dir, pet_name}。

    项目配置了 LLM_API_KEY 时走真实模型；否则用规则兜底（前端仍可正常安装）。
    """
    try:
        from app.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
    except Exception:
        return {}

    if not LLM_API_KEY:
        return {}

    prompt = (
        "你是一个 DSH 桌宠包安装助手。下面是一个 git 仓库的文件树，里面包含一个桌宠包"
        "（WebM 动画 + 配置文件，配置文件可能是 config.json / pet.json / *-config.json）。\n\n"
        f"仓库地址：{git_url}\n\n文件树：\n{tree}\n\n"
        "请找出：1) 宠物配置文件路径 2) WebM 动画所在目录 3) 宠物名称。\n"
        "只输出 JSON，格式：{\"config_path\": \"...\", \"webm_dir\": \"...\", \"pet_name\": \"...\"}，"
        "找不到某项就填空字符串。"
    )

    try:
        from openai import OpenAI
        client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=300,
        )
        text = resp.choices[0].message.content or ""
        # 提取 JSON
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
    except Exception as e:
        logger.warning("[pet-market] AI 分析失败，回退规则: %s", e)
    return {}


# ── API ────────────────────────────────────────────────────

@router.get("/ai/pet-market/pets")
def list_pets(user_id: Optional[int] = Depends(get_optional_user_id)):
    """已安装宠物 + 预置市场清单 + 当前宠物。"""
    current = None
    if user_id:
        cfg = pet_assets.load_user_config(user_id)
        current = (cfg.get("settings") or {}).get("petId") or None
    return {
        "ok": True,
        "installed": pet_market.list_installed_pets(),
        "market": pet_market.preset_market(),
        "current_pet": current,
    }


@router.post("/ai/pet-market/install")
def install_pet(req: InstallReq, user_id: Optional[int] = Depends(get_optional_user_id)):
    """通过 git 链接安装宠物包（可选 AI 辅助识别）。"""
    _require_user(user_id)
    result = pet_market.install_from_git(req.git_url, req.pet_id)

    # AI 辅助：规则识别失败时，用 LLM 分析后重试（定位 pet_id）
    if not result.get("ok") and req.use_ai:
        try:
            tmp = Path(tempfile.mkdtemp(prefix="pet-ai-"))
            subprocess.run(
                ["git", "clone", "--depth", "1", req.git_url, str(tmp / "repo")],
                capture_output=True, text=True, timeout=300,
                encoding="utf-8", errors="replace",
            )
            repo = tmp / "repo"
            if repo.exists():
                tree = _tree(repo)
                hint = _ai_analyze(req.git_url, tree)
                if hint.get("pet_name"):
                    result = pet_market.install_from_git(req.git_url, hint.get("pet_name"))
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception as e:
            logger.warning("[pet-market] AI 辅助安装失败: %s", e)

    return result


@router.post("/ai/pet-market/switch")
def switch_pet(req: SwitchReq, user_id: Optional[int] = Depends(get_optional_user_id)):
    """切换当前桌宠（None = 默认大肥鱼）。"""
    uid = _require_user(user_id)
    cfg = pet_assets.load_user_config(uid)
    settings = dict(cfg.get("settings") or {})
    if req.pet_id:
        # 校验宠物已安装
        if not pet_market.pet_dir(req.pet_id).exists():
            raise HTTPException(status_code=404, detail="宠物未安装")
        settings["petId"] = pet_market._safe_id(req.pet_id)
    else:
        settings.pop("petId", None)
    cfg["settings"] = settings
    pet_assets.save_user_config(uid, cfg)
    return {"ok": True, "pet_id": req.pet_id}


@router.delete("/ai/pet-market/pets/{pet_id}")
def delete_pet(pet_id: str, user_id: Optional[int] = Depends(get_optional_user_id)):
    """卸载宠物。"""
    _require_user(user_id)
    # 若当前正在使用该宠物，先切回默认
    cfg = pet_assets.load_user_config(user_id)
    if (cfg.get("settings") or {}).get("petId") == pet_market._safe_id(pet_id):
        settings = dict(cfg.get("settings") or {})
        settings.pop("petId", None)
        cfg["settings"] = settings
        pet_assets.save_user_config(user_id, cfg)
    result = pet_market.uninstall_pet(pet_id)
    return result
