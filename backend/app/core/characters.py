"""
角色系统 —— 角色包加载、人设构建、用户偏好管理。

角色包 = /plugins/characters/ 目录下的 JSON 文件，标准结构见 maid.json。
- 内置角色：maid（蓝发小女仆，即原大肥鱼）、senpai、cool、heal、brat
- 用户偏好（收藏/置顶/人设参数开关）持久化在 User.character_prefs（JSON）
- 会话绑定角色持久化在 ChatSession.character_id
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from app.core.db import SessionLocal
from app.core.db.models import User

logger = logging.getLogger(__name__)

# 角色包目录
CHARACTERS_DIR = Path(__file__).resolve().parent.parent / "plugins" / "characters"

# 默认人设参数开关
DEFAULT_SETTINGS = {
    "active_message": True,      # 主动发消息：开/关
    "tone": "normal",            # 语气浓度：light清淡 / normal正常 / clingy黏人
    "meme_frequency": "normal",  # 表情包频率：low少 / normal适中 / high多
    "memory_sensitivity": "high" # 记忆敏感度：low只记大事 / high记住细碎小事
}

# 默认角色 ID（内置初始女仆）
DEFAULT_CHARACTER_ID = "maid"

# 用户偏好默认结构
DEFAULT_PREFS = {
    "favorites": [],             # 收藏的角色 ID 列表
    "pinned": [],                # 置顶的角色 ID 列表
    "current_character": DEFAULT_CHARACTER_ID,
    "settings": dict(DEFAULT_SETTINGS),
}


def load_character(char_id: str) -> Optional[dict]:
    """从角色包目录加载单个角色 JSON。"""
    if not char_id:
        return None
    # 防止路径穿越
    safe_id = "".join(c for c in char_id if c.isalnum() or c in "-_")
    if safe_id != char_id:
        return None
    path = CHARACTERS_DIR / f"{safe_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("id", safe_id)
        return data
    except Exception as e:
        logger.warning("[characters] 加载角色 %s 失败: %s", char_id, e)
        return None


def list_characters() -> List[dict]:
    """列出所有内置角色（按置顶优先，其余按文件名排序）。"""
    chars = []
    if CHARACTERS_DIR.exists():
        for p in sorted(CHARACTERS_DIR.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                data.setdefault("id", p.stem)
                chars.append(data)
            except Exception as e:
                logger.warning("[characters] 解析 %s 失败: %s", p.name, e)
    return chars


def build_character_prompt(char: dict, settings: Optional[dict] = None) -> str:
    """根据角色包 + 人设参数开关，构建 system prompt。

    角色包结构：
      persona: 基础人设
      rules:   硬性规则列表
      style:   说话风格配置（short_sentences / meme_frequency / active_topics / tone）
      emotions: 情绪台词库（暂不直接注入 prompt，由表情包映射使用）

    人设参数开关（settings）会覆盖角色默认 style：
      - tone: light/normal/clingy → 追加语气浓度指令
      - meme_frequency: low/normal/high → 追加颜文字频率指令
      - active_topics（或 active_message）→ 追加是否主动发起话题指令
      - memory_sensitivity: low/high → 追加记忆敏感度指令
    """
    settings = settings or {}
    persona = char.get("persona", "")
    rules = char.get("rules", [])

    parts = [persona]
    if rules:
        parts.append("硬性规则（必须严格执行）：")
        parts += [f"{i+1}. {r}" for i, r in enumerate(rules)]

    # ── 人设参数开关注入 ──
    style = char.get("style", {})
    tone = settings.get("tone") or style.get("tone") or "normal"
    meme = settings.get("meme_frequency") or style.get("meme_frequency") or "normal"
    active = settings.get("active_message")
    if active is None:
        active = style.get("active_topics", True)
    mem_sens = settings.get("memory_sensitivity", "high")

    extra = []

    # 语气浓度
    tone_map = {
        "light": "语气清淡一些，别太黏人，保持点距离感，自然就好。",
        "normal": "语气正常自然，像熟人聊天。",
        "clingy": "语气可以黏人一点，多撒娇、多表达想念和依赖，主动靠近对方。",
    }
    extra.append("【语气浓度】" + tone_map.get(tone, tone_map["normal"]))

    # 表情包频率（颜文字频率）
    meme_map = {
        "low": "颜文字尽量少用，一两条消息里最多一个，多靠文字本身的情绪。",
        "normal": "颜文字适量使用，贴合情绪，不要每句都带。",
        "high": "颜文字可以多用一点，让聊天更活泼，但也不要每句都刷屏。",
    }
    extra.append("【颜文字频率】" + meme_map.get(meme, meme_map["normal"]))

    # 主动发起话题
    if active:
        extra.append("【主动发起话题】偶尔主动抛出小话题延续对话，不要只会被动应答。")
    else:
        extra.append("【主动发起话题】不要主动抛出话题，专注回应对方，对方不主动就不延伸。")

    # 记忆敏感度
    mem_map = {
        "low": "只记住对方说过的关键大事（如重要经历、重大决定），细碎小事不必刻意记。",
        "high": "尽量记住对方说过的细碎小事（喜好、习惯、随口提过的细节），并在合适时机自然呼应。",
    }
    extra.append("【记忆敏感度】" + mem_map.get(mem_sens, mem_map["high"]))

    parts.extend(extra)
    return "\n".join(parts)


def get_user_prefs(user_id: Optional[int]) -> dict:
    """读取用户角色偏好（收藏/置顶/当前角色/人设参数）。未登录返回默认。"""
    if not user_id:
        return dict(DEFAULT_PREFS)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.character_prefs:
            return dict(DEFAULT_PREFS)
        prefs = dict(user.character_prefs)
        # 补齐缺失字段
        for k, v in DEFAULT_PREFS.items():
            prefs.setdefault(k, dict(v) if isinstance(v, dict) else v)
        prefs["settings"] = {**DEFAULT_SETTINGS, **(prefs.get("settings") or {})}
        return prefs
    finally:
        db.close()


def save_user_prefs(user_id: int, prefs: dict) -> dict:
    """保存用户角色偏好。"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return prefs
        merged = dict(user.character_prefs or {})
        merged.update(prefs)
        user.character_prefs = merged
        db.commit()
        return merged
    finally:
        db.close()


def get_user_settings(user_id: Optional[int]) -> dict:
    """读取人设参数开关。"""
    prefs = get_user_prefs(user_id)
    return {**DEFAULT_SETTINGS, **(prefs.get("settings") or {})}


def save_user_settings(user_id: int, settings: dict) -> dict:
    """保存人设参数开关。"""
    prefs = get_user_prefs(user_id)
    prefs["settings"] = {**DEFAULT_SETTINGS, **(prefs.get("settings") or {}), **settings}
    save_user_prefs(user_id, {"settings": prefs["settings"]})
    return prefs["settings"]


def get_current_character_id(user_id: Optional[int]) -> str:
    """获取用户当前绑定角色 ID。"""
    prefs = get_user_prefs(user_id)
    return prefs.get("current_character") or DEFAULT_CHARACTER_ID


def resolve_character(char_id: Optional[str], user_id: Optional[int] = None) -> Optional[dict]:
    """解析角色：优先用指定 char_id，否则用用户当前绑定角色，最后回退默认女仆。"""
    cid = char_id or get_current_character_id(user_id) or DEFAULT_CHARACTER_ID
    char = load_character(cid)
    if not char:
        char = load_character(DEFAULT_CHARACTER_ID)
    return char


def get_opening(char_id: Optional[str]) -> str:
    """获取角色开场白。"""
    char = load_character(char_id or DEFAULT_CHARACTER_ID)
    return (char or {}).get("opening", "")
