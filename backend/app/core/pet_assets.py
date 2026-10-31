"""
宠物自定义资源管理（dsh-pet 用户层）。

目录布局（每个用户一份）：
    ops/data/pet_assets/<user_id>/
    ├── webm/          # 用户上传的宠物动画（.webm）
    ├── memes/         # 用户上传的表情包（.png/.gif/.jpg）
    ├── sound/         # 用户上传的音效（.webm/.wav/.mp3）
    └── config.json    # 用户触发条件 / memes 描述 / 音效映射 / 全局开关

内置默认资源在 front/static/plugins/dsh-pet/assets/（只读，随版本发布）。
用户资源与内置资源合并后由 GET /plugins/dsh-pet/config 返回给桌宠前端。
"""
import json
import logging
import re
from pathlib import Path
from typing import Optional

from app.core.paths import data_dir

logger = logging.getLogger(__name__)

# 用户资源根目录
PET_ASSETS_ROOT = data_dir() / "pet_assets"

# 允许的上传类型与扩展名
ALLOWED_EXTS = {
    "webm": {".webm"},
    "meme": {".png", ".gif", ".jpg", ".jpeg", ".webp"},
    "sound": {".webm", ".wav", ".mp3", ".ogg"},
}

# 资源类型 → 目录名
KIND_DIR = {
    "webm": "webm",
    "meme": "memes",
    "sound": "sound",
}

# 内置动画池（与 pet.js 硬编码一致，作为默认值；用户配置覆盖/追加）
DEFAULT_POOLS = {
    "idle": ["待机呼吸休闲"],
    "turn": ["东张西望"],
    "drag": ["被鼠标拖拽悬空反馈"],
    "clicks": [
        "点击回应-开心跃动", "点击回应-害羞惊讶", "点击回应-傲娇生气",
        "点击回应-挠痒咯咯笑", "点击回应-元气挥手",
    ],
    "moves": ["螃蟹走路", "原地漂浮踏步", "原地左转奔跑"],
    "random": [
        "悠闲哼歌", "超大伸懒腰", "原地敲击桌面互动", "原地重力下蹲压缩", "哈欠连天",
        "原地小憩沉眠", "女仆屈膝礼仪", "被吓一跳", "小幅度原地360度旋转展示",
        "偷吃零食被抓住", "用鲸鱼尾巴拍打地面", "打瞌睡被惊醒", "照镜子", "整体换装试色",
        "轻快记录", "写代码", "摇扇纳凉", "晨间刷牙", "原地专心玩魔方", "原地蹲下玩玩具汽车",
        "鲸鱼吐泡泡特效", "原地跳跃抓碎头顶物品", "玩游戏气急败坏", "玩水枪",
        "小提琴演奏", "蓝鲸现世", "优雅女仆舞", "轻快摇摆舞", "可爱宅舞", "吹气球",
        "动物环绕", "放风筝", "拆礼物", "变鸽子", "扑克魔术", "抽陀螺", "吹笛子",
        "蝴蝶蜜蜂环绕头顶开花", "撸猫", "凭空生花", "骑木马", "三球抛接", "踢毽子",
        "下五子棋", "荡秋千", "吃白饭", "大口吃零食", "吃Token", "吃早餐", "吃午餐",
        "吃晚餐", "吃冰淇淋融化", "吃大闸蟹", "吃糖葫芦", "吃长寿面", "吃西瓜", "涮火锅",
    ],
    "seasonal": [
        "被落叶淹没", "中秋赏月吃月饼", "堆雪人", "放烟花", "吃粽子", "吃年糕", "吃青团",
        "吃腊八粥", "吃重阳糕", "收红包", "写福字", "穿针乞巧", "舞狮头", "讨糖南瓜灯",
        "插茱萸赏菊", "放河灯", "萌化小幽灵", "装点圣诞树", "放孔明灯", "吃汤圆", "吃饺子",
    ],
    "textMeme": ["是啊，吃什么", "深度思考碎碎念"],
    "whisper": ["碎碎念-擦桌碎碎念", "碎碎念-发呆碎碎念", "碎碎念-对屏碎碎念"],
    "workStatus": [
        "工作状态-思考冒泡", "工作状态-忙碌点按", "工作状态-清点归档",
        "工作状态-原地踱步张望", "工作状态-雀跃庆祝", "工作状态-垂头叹气冒汗",
    ],
}

# 内置表情包映射（名称 → 描述）
DEFAULT_MEMES = {
    "吃白饭的大肥鱼": "躺平扒白饭，摆烂挨骂也无所谓",
    "大的要来啦": "举喇叭大喊预警",
    "大的药来了": "抱着超大胶囊，谐音梗",
    "要不直接骂他": "气愤指着前方要骂人",
    "死掉了": "翻肚皮躺平灵魂出窍",
    "深度睡眠": "趴着呼呼大睡冒 Zzz",
    "大烧货": "死鱼眼吐槽想得慢",
    "先养着吧": "搂着一群小鲸鱼",
    "吃饱饱摸肚子": "侧躺拍肚子说吃饱饱",
    "誓死践行开源精神": "庄重敬礼表态",
    "电死你": "举电击器放电",
    "可爱": "标准正面卖萌立绘",
    "token给妈妈保管": "伸手过来要 token",
}

# 触发池的 UI 名称（供前端展示）
POOL_LABELS = {
    "idle": "待机",
    "turn": "转向",
    "drag": "拖拽",
    "clicks": "点击回应",
    "moves": "移动",
    "random": "随机小动作",
    "seasonal": "时节",
    "textMeme": "文字梗",
    "whisper": "碎碎念",
    "workStatus": "工作状态",
}


def _safe_name(name: str) -> str:
    """清洗文件名：只保留安全字符，去掉路径穿越与非法字符。"""
    name = (name or "").strip()
    name = re.sub(r"[^\w\u4e00-\u9fff\-. ]", "_", name)
    name = name.replace("..", "_").replace("/", "_").replace("\\", "_")
    name = name.strip().strip(".")
    return name[:120]


def user_dir(user_id: int) -> Path:
    d = PET_ASSETS_ROOT / str(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def kind_dir(user_id: int, kind: str) -> Path:
    d = user_dir(user_id) / KIND_DIR.get(kind, kind)
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_file(user_id: int) -> Path:
    return user_dir(user_id) / "config.json"


def load_user_config(user_id: int) -> dict:
    """读用户配置（不存在返回空字典）。"""
    f = config_file(user_id)
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("读取宠物配置失败: %s", e)
            return {}
    return {}


def save_user_config(user_id: int, cfg: dict) -> dict:
    """保存用户配置（校验 + 清洗）。"""
    clean = {
        "pools": {},
        "memes": {},
        "sounds": {},
        "settings": {},
    }
    pools = cfg.get("pools") or {}
    if isinstance(pools, dict):
        for k in POOL_LABELS:
            v = pools.get(k)
            if isinstance(v, list):
                clean["pools"][k] = [_safe_name(x) for x in v if str(x).strip()]

    memes = cfg.get("memes") or {}
    if isinstance(memes, dict):
        for k, v in memes.items():
            kk = _safe_name(k)
            if kk:
                clean["memes"][kk] = str(v)[:200]

    sounds = cfg.get("sounds") or {}
    if isinstance(sounds, dict):
        for k, v in sounds.items():
            kk = _safe_name(k)
            if kk:
                clean["sounds"][kk] = str(v)[:200]

    settings = cfg.get("settings") or {}
    if isinstance(settings, dict):
        clean["settings"] = {
            "clickSoundEnabled": bool(settings.get("clickSoundEnabled", True)),
            "whisperEnabled": bool(settings.get("whisperEnabled", True)),
        }
        # 保留当前宠物选择（插件市场切换）
        pet_id = settings.get("petId")
        if pet_id:
            clean["settings"]["petId"] = str(pet_id)

    config_file(user_id).write_text(
        json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return clean


def merged_config(user_id: Optional[int]) -> dict:
    """合并内置默认 + 用户配置 + 当前安装的宠物，返回桌宠前端可直接消费的成品。"""
    user_cfg = load_user_config(user_id) if user_id else {}

    # ── 当前宠物（插件市场安装的 DSH pet 包）──
    current_pet = (user_cfg.get("settings") or {}).get("petId")
    pet_pools = {}
    pet_dir_url = None
    pet_meta = {}
    pet_memes = {}        # 当前宠物自带的表情包 {名称: 描述}
    pet_meme_names = []   # 名称列表（前端 resolveAsset 判断用）
    if current_pet:
        try:
            from app.core import pet_market
            cfg = pet_market.load_pet_config(current_pet)
            pet_pools = cfg.get("pools") or {}
            pdir = pet_market.pet_dir(current_pet)
            if pdir.exists():
                pet_dir_url = f"/plugins/pets/{pet_market._safe_id(current_pet)}"
                pet_meta = {"id": current_pet, "name": cfg.get("name") or current_pet}
                # 宠物自带表情包：扫描 memes/ 目录（png/gif/jpg/webp）
                memes_dir = pdir / "memes"
                if memes_dir.exists():
                    for p in sorted(memes_dir.iterdir()):
                        if p.is_file() and p.suffix.lower() in ALLOWED_EXTS["meme"]:
                            # 描述优先取 config 里的 memes 映射，没有就用文件名
                            desc = (cfg.get("memes") or {}).get(p.stem, "")
                            pet_memes[p.stem] = desc
                    pet_meme_names = list(pet_memes.keys())
        except Exception as e:
            logger.warning("[pet] 加载当前宠物失败: %s", e)

    # 动画池：内置 + 用户追加（有当前宠物时，完全用宠物池覆盖内置池）
    pools = {k: list(v) for k, v in DEFAULT_POOLS.items()}
    if pet_pools:
        # 切换到宠物后：宠物池完全接管，缺失的池置空（避免回退内置大肥鱼动画导致 404）
        for k in pools:
            pools[k] = list(pet_pools.get(k) or [])
    else:
        user_pools = user_cfg.get("pools") or {}
        for k, extra in user_pools.items():
            if k in pools and isinstance(extra, list):
                for name in extra:
                    if name and name not in pools[k]:
                        pools[k].append(name)

    # 表情包：
    #  - 切到外部宠物包时，只用该宠物自带的表情包（可能为空 → 碎碎念就不配图，
    #    绝不回退到大肥鱼表情包，避免「用肆喵发的却是大肥鱼表情」）。
    #  - 默认（大肥鱼）时：内置 + 用户追加。
    if current_pet and pet_dir_url:
        memes = dict(pet_memes)
    else:
        memes = dict(DEFAULT_MEMES)
        user_memes = user_cfg.get("memes") or {}
        for k, v in user_memes.items():
            memes[k] = v

    # 音效：用户为主（内置只有 click-duck.wav）
    sounds = {}
    user_sounds = user_cfg.get("sounds") or {}
    for k, v in user_sounds.items():
        sounds[k] = v

    settings = {
        "clickSoundEnabled": True,
        "whisperEnabled": True,
    }
    user_settings = user_cfg.get("settings") or {}
    settings.update(user_settings)

    # 用户上传的资源清单（供前端判断路径）
    user_assets = {}
    if user_id:
        u = user_dir(user_id)
        user_assets = {
            "webm": sorted(p.stem for p in (u / "webm").glob("*.webm")) if (u / "webm").exists() else [],
            "memes": sorted(p.stem for p in (u / "memes").glob("*") if p.suffix.lower() in ALLOWED_EXTS["meme"]) if (u / "memes").exists() else [],
            "sound": sorted(p.stem for p in (u / "sound").glob("*") if p.suffix.lower() in ALLOWED_EXTS["sound"]) if (u / "sound").exists() else [],
        }

    return {
        "pools": pools,
        "memes": memes,
        "sounds": sounds,
        "settings": settings,
        "userAssets": user_assets,
        "poolLabels": POOL_LABELS,
        "userDir": f"/plugins/dsh-pet/user-assets/{user_id}" if user_id else None,
        "petDir": pet_dir_url,
        "currentPet": pet_meta,
        "petMemes": pet_meme_names,
    }


def save_upload(user_id: int, kind: str, filename: str, content: bytes) -> dict:
    """保存上传的资源，返回 {ok, name, url, error}。"""
    if kind not in ALLOWED_EXTS:
        return {"ok": False, "error": f"未知资源类型: {kind}"}
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTS[kind]:
        allowed = " ".join(ALLOWED_EXTS[kind])
        return {"ok": False, "error": f"扩展名 {ext} 不允许，仅支持 {allowed}"}

    stem = _safe_name(Path(filename).stem)
    if not stem:
        return {"ok": False, "error": "文件名非法"}

    # 限制大小（webm 20MB，meme 5MB，sound 10MB）
    max_size = {"webm": 20 * 1024 * 1024, "meme": 5 * 1024 * 1024, "sound": 10 * 1024 * 1024}[kind]
    if len(content) > max_size:
        return {"ok": False, "error": f"文件超过大小限制（{max_size // (1024 * 1024)}MB）"}

    target_dir = kind_dir(user_id, kind)
    target = target_dir / f"{stem}{ext}"
    # 同名覆盖
    target.write_bytes(content)

    url = f"/plugins/dsh-pet/user-assets/{user_id}/{KIND_DIR[kind]}/{stem}{ext}"
    return {"ok": True, "name": stem, "url": url}


def delete_resource(user_id: int, kind: str, name: str) -> dict:
    """删除用户资源。"""
    if kind not in ALLOWED_EXTS:
        return {"ok": False, "error": f"未知资源类型: {kind}"}
    stem = _safe_name(name)
    if not stem:
        return {"ok": False, "error": "名称非法"}
    target_dir = kind_dir(user_id, kind)
    deleted = False
    for ext in ALLOWED_EXTS[kind]:
        p = target_dir / f"{stem}{ext}"
        if p.exists():
            p.unlink()
            deleted = True
    return {"ok": deleted, "name": stem}
