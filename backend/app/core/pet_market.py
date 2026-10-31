"""
DSH 宠物插件市场 —— git 链接导入 DSH pet 包（WebM 动画 + config.json）。

安装流程：
  1. git clone（浅克隆）或 GitHub API 下载到临时目录
  2. 扫描识别：找到 pet 配置文件（config.json / *-config.json）+ 全部 .webm 动画
  3. 复制到 front/static/plugins/pets/<pet_id>/{webm/*.webm, config.json, preview.png}
  4. 写 meta.json（名称、git 地址、安装时间）

目录布局：
    front/static/plugins/pets/<pet_id>/
    ├── webm/            # 动画（.webm）
    ├── config.json      # 动画池配置（animations → pools）
    ├── preview.png      # 预览图（可选）
    └── meta.json        # 安装元信息

当前宠物选择存在用户 config.json 的 settings.petId 里（pet_assets.merged_config 消费）。
"""
import json
import logging
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import List, Optional

from app.core.paths import project_root

logger = logging.getLogger(__name__)

# 宠物安装根目录（与 dsh-pet 同级）
PETS_ROOT = project_root() / "front" / "static" / "plugins" / "pets"

# 预置市场清单（仅 DSH WebM 生态）
PRESET_MARKET = [
    {
        "pet_id": "simiao",
        "name": "肆喵 Simiao",
        "desc": "黑灰小猫娘，思考动画很多，和大肥鱼同社区画风",
        "git": "https://github.com/sijin14514-sys/simiao-dsh-pet.git",
        "tags": ["猫娘", "DSH"],
    },
]


def _safe_id(s: str) -> str:
    """清洗宠物 ID：只保留字母数字 - _。"""
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9\-_]", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:40] or "pet"


def pet_dir(pet_id: str) -> Path:
    return PETS_ROOT / _safe_id(pet_id)


def _read_jsonc(path: Path) -> dict:
    """读 JSON/JSONC（去 // 与 /* */ 注释）。"""
    raw = path.read_text(encoding="utf-8", errors="replace")
    raw = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)
    raw = re.sub(r"//[^\n]*", "", raw)
    # 去掉 JSON 不允许的尾逗号
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    try:
        return json.loads(raw)
    except Exception as e:
        logger.warning("[pet-market] 解析 JSONC 失败 %s: %s", path, e)
        return {}


def _find_pet_files(repo: Path) -> dict:
    """扫描 git 仓库，识别 pet 配置 + webm 动画 + 预览图（DSH WebM 生态）。

    返回 {config_path, config_data, webm_files, preview_path}
    """
    # 1. 找配置文件：config.json / *-config.json / *.jsonc
    config_path = None
    config_data = {}
    candidates = sorted(repo.rglob("*")) if repo.exists() else []
    config_names = {"config.json", "pet-config.json"}
    for p in candidates:
        if not p.is_file():
            continue
        low = p.name.lower()
        if low in config_names or (low.endswith("-config.json") or low.endswith("config.jsonc")):
            d = _read_jsonc(p)
            if d:
                # 优先选择含 pets / animations 字段的配置
                if "pets" in d or "animations" in d or "animationWeights" in d:
                    config_path = p
                    config_data = d
                    break
                if config_path is None:
                    config_path = p
                    config_data = d

    # 2. 找 webm 动画
    webm_files = []
    for p in sorted(repo.rglob("*.webm")):
        if p.is_file() and ".git" not in p.parts:
            webm_files.append(p)

    # 3. 找预览图
    preview_path = None
    for name in ("preview.png", "preview.webp", "preview.jpg", "cover.png", "logo.png"):
        for p in sorted(repo.rglob(name)):
            if p.is_file() and ".git" not in p.parts:
                preview_path = p
                break
        if preview_path:
            break

    return {
        "config_path": config_path,
        "config_data": config_data,
        "webm_files": webm_files,
        "preview_path": preview_path,
    }


def _config_to_pools(config_data: dict) -> dict:
    """把 DSH config.json 的 animations 结构转成 pet.js 的 pools。

    DSH config: animations = {idle:[...], turn:[...], drag:[...], clicks:[...],
                              moves:{actions:[{name}]}, categories:[{id,actions}], events:{...}}
    pet.js pools: idle/turn/drag/clicks/moves/random/seasonal/textMeme/whisper/workStatus
    """
    anims = config_data.get("animations", {}) if isinstance(config_data, dict) else {}
    pools = {}

    def _list(v):
        if isinstance(v, list):
            return [x for x in v if isinstance(x, str)]
        return []

    pools["idle"] = _list(anims.get("idle"))
    pools["turn"] = _list(anims.get("turn"))
    pools["drag"] = _list(anims.get("drag"))
    pools["clicks"] = _list(anims.get("clicks"))

    # moves: {actions:[{name}]}
    moves = anims.get("moves", {})
    move_names = []
    if isinstance(moves, dict):
        actions = moves.get("actions", [])
        move_names = [a.get("name") for a in actions if isinstance(a, dict) and a.get("name")]
    elif isinstance(moves, list):
        move_names = [m for m in moves if isinstance(m, str)]
    pools["moves"] = move_names

    # categories: [{id, actions:[...]}] → 合并成 random
    random_pool = []
    for cat in anims.get("categories", []):
        if isinstance(cat, dict):
            random_pool.extend(_list(cat.get("actions")))
    pools["random"] = random_pool

    # seasonal（DSH 一般没有，留空）
    pools["seasonal"] = _list(anims.get("seasonal"))
    pools["textMeme"] = _list(anims.get("textMeme"))
    pools["whisper"] = _list(anims.get("whisper"))
    pools["workStatus"] = _list(anims.get("workStatus"))

    # events.balance 等 → 并入 random（当作随机动作）
    # 兼容嵌套数组（DSH 复合动画：["号又没了", "钱包倒空"] 表示两个 webm 连播）
    events = anims.get("events", {})
    if isinstance(events, dict):
        for ev in events.values():
            if isinstance(ev, list):
                for item in ev:
                    if isinstance(item, str):
                        random_pool.append(item)
                    elif isinstance(item, list):
                        # 复合动画：把子项拆开各自入池（保证 webm 都能被引用）
                        random_pool.extend(x for x in item if isinstance(x, str))
    pools["random"] = list(dict.fromkeys(random_pool))

    return pools


def _parse_github(git_url: str) -> Optional[tuple]:
    """解析 github.com 链接为 (owner, repo, branch)。非 github 返回 None。"""
    m = re.match(
        r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/tree/([^/]+))?/?$",
        git_url.strip(),
    )
    if not m:
        return None
    owner, repo, branch = m.group(1), m.group(2), (m.group(3) or "main")
    return owner, repo, branch


def _http_get_json(url: str, timeout: int = 40, retries: int = 3) -> dict:
    """GET 一个 JSON 端点，返回 dict/list。网络抖动时自动重试。"""
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "jingent-pet-market/1.0",
                "Accept": "application/vnd.github+json",
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as e:
            last_err = e
            logger.warning("[pet-market] GET 失败(第%d次) %s: %s", attempt + 1, url, e)
            time.sleep(1.5 * (attempt + 1))
    raise last_err


def _http_download(url: str, dest: Path, timeout: int = 120, retries: int = 3) -> bool:
    """下载单个文件到 dest。成功返回 True。网络抖动时自动重试。"""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "jingent-pet-market/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, "wb") as f:
                    shutil.copyfileobj(resp, f)
            return True
        except Exception as e:
            logger.warning("[pet-market] 下载失败(第%d次) %s: %s", attempt + 1, url, e)
            time.sleep(1.5 * (attempt + 1))
    return False


def _download_github(git_url: str, dest_dir: Path, branch: str = None) -> bool:
    """用 GitHub API 把仓库文件下载到 dest_dir（绕过 git pack 传输限制）。

    下载 DSH pet 文件：*.webm、config.json、预览图。
    返回是否成功（至少下载到 webm）。
    """
    parsed = _parse_github(git_url)
    if not parsed:
        return False
    owner, repo, url_branch = parsed
    branch = branch or url_branch

    # 1. 递归树
    tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    try:
        tree = _http_get_json(tree_url)
    except Exception as e:
        logger.warning("[pet-market] GitHub 树获取失败: %s", e)
        return False

    items = tree.get("tree", []) if isinstance(tree, dict) else []
    webm_items = []
    config_items = []
    preview_items = []
    for it in items:
        path = it.get("path", "")
        if it.get("type") != "blob":
            continue
        low = path.lower()
        if low.endswith(".webm"):
            webm_items.append(path)
        elif low in ("config.json",) or low.endswith("-config.json") or low.endswith("config.jsonc"):
            config_items.append(path)
        elif low.endswith((".png", ".webp", ".jpg", ".jpeg")) and any(
            k in low for k in ("preview", "cover", "logo", "avatar")
        ):
            preview_items.append(path)

    if not webm_items:
        return False

    raw_base = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/"

    # 2. 下载 webm（并发下载）
    from concurrent.futures import ThreadPoolExecutor, as_completed
    webm_list = webm_items[:80]
    downloaded = 0

    def _dl(path):
        encoded = urllib.parse.quote(path, safe="/")
        fname = Path(path).name
        return _http_download(raw_base + encoded, dest_dir / "webm" / fname)

    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(_dl, p): p for p in webm_list}
        for fut in as_completed(futs):
            if fut.result():
                downloaded += 1

    if downloaded == 0:
        return False

    # 3. 下载配置文件 + 预览图
    for path in config_items[:5]:
        encoded = urllib.parse.quote(path, safe="/")
        fname = Path(path).name
        _http_download(raw_base + encoded, dest_dir / "configs" / fname)
    for path in preview_items[:3]:
        encoded = urllib.parse.quote(path, safe="/")
        fname = Path(path).name
        _http_download(raw_base + encoded, dest_dir / "preview" / fname)

    return True


def install_from_git(git_url: str, pet_id: Optional[str] = None) -> dict:
    """git 安装一个 DSH pet 包。返回 {ok, pet_id, name, pools, webm_count, error}。"""
    git_url = (git_url or "").strip()
    if not git_url.startswith(("http://", "https://", "git@", "ssh://")):
        return {"ok": False, "error": "请输入有效的 git 链接（http/https/ssh）"}

    tmp = Path(tempfile.mkdtemp(prefix="pet-install-"))
    try:
        repo = tmp / "repo"
        cloned = False

        # GitHub 仓库走 API 下载（绕过 git pack 传输限制）
        if _parse_github(git_url):
            logger.info("[pet-market] GitHub 仓库走 API 下载 %s", git_url)
            cloned = _download_github(git_url, repo)

        # 非 GitHub 或 API 失败 → git clone 兜底（重试 2 次）
        if not cloned:
            logger.info("[pet-market] git clone %s", git_url)
            for attempt in range(2):
                try:
                    proc = subprocess.run(
                        ["git", "clone", "--depth", "1", git_url, str(repo)],
                        capture_output=True, text=True, timeout=90,
                        encoding="utf-8", errors="replace",
                    )
                    if proc.returncode == 0 and repo.exists():
                        cloned = True
                        break
                    logger.warning("[pet-market] git clone 失败(第%d次): %s",
                                   attempt + 1, (proc.stderr or "")[:200])
                except subprocess.TimeoutExpired:
                    logger.warning("[pet-market] git clone 超时(第%d次)", attempt + 1)
                # 重试前清掉残留
                shutil.rmtree(repo, ignore_errors=True)
                time.sleep(2)

        if not cloned:
            return {"ok": False, "error": "仓库下载失败（请检查链接或网络）"}

        found = _find_pet_files(repo)

        if not found["webm_files"]:
            # 合集仓（catalog.json 索引多个子包）需要进到子目录安装，给出可操作提示
            is_collection = any(
                (repo / n).exists() for n in ("catalog.json", "pets", "packages")
            )
            if is_collection:
                return {"ok": False, "error": "这是一个合集仓库，请打开仓库找到单个宠物子目录的 git 地址再安装（如 .../tree/main/pets/xxx）"}
            return {"ok": False, "error": "仓库里没找到 .webm 动画文件，不是有效的 DSH pet 包"}

        # 确定 pet_id（优先参数，其次 config 的 pets[0].id，其次 git 仓库名）
        config_data = found["config_data"]
        if not pet_id:
            if isinstance(config_data, dict) and config_data.get("pets"):
                pets0 = config_data["pets"][0]
                if isinstance(pets0, dict) and pets0.get("id"):
                    pet_id = pets0["id"]
            if not pet_id:
                repo_name = Path(git_url.rstrip("/")).name
                pet_id = repo_name.replace(".git", "")
        pid = _safe_id(pet_id)

        name = pid
        if isinstance(config_data, dict) and config_data.get("pets"):
            first = config_data["pets"][0]
            if isinstance(first, dict) and first.get("name"):
                name = first["name"]

        # 目标目录
        target = pet_dir(pid)
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)

        # 复制 webm
        webm_target = target / "webm"
        webm_target.mkdir(parents=True, exist_ok=True)
        for f in found["webm_files"]:
            shutil.copy2(f, webm_target / f.name)

        pools = _config_to_pools(config_data)

        # 写 config.json（转成 pet.js 可消费的 pools）
        config_out = {
            "name": name,
            "id": pid,
            "pools": pools,
        }
        (target / "config.json").write_text(
            json.dumps(config_out, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # 复制预览图
        if found["preview_path"]:
            shutil.copy2(found["preview_path"], target / "preview.png")

        # meta.json
        meta = {
            "pet_id": pid,
            "name": name,
            "git": git_url,
            "installed_at": int(time.time() * 1000),
            "webm_count": len(found["webm_files"]),
        }
        (target / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # 统计各动画池的数量（供前端展示识别结果）
        pool_counts = {k: len(v) for k, v in pools.items() if v}
        return {
            "ok": True,
            "pet_id": pid,
            "name": name,
            "pools": pools,
            "webm_count": len(found["webm_files"]),
            "detail": {
                "type": "webm",
                "webm_count": len(found["webm_files"]),
                "pool_counts": pool_counts,
                "has_preview": bool(found["preview_path"]),
            },
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "git clone 超时（仓库可能太大）"}
    except Exception as e:
        logger.exception("[pet-market] 安装失败")
        return {"ok": False, "error": f"安装失败：{e}"}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def list_installed_pets() -> List[dict]:
    """列出已安装的宠物（扫描 pets/ 目录）。"""
    PETS_ROOT.mkdir(parents=True, exist_ok=True)
    result = []
    for d in sorted(PETS_ROOT.iterdir()):
        if not d.is_dir():
            continue
        meta_path = d / "meta.json"
        meta = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
        config_path = d / "config.json"
        config = {}
        if config_path.exists():
            config = _read_jsonc(config_path)
        webm_count = len(list((d / "webm").glob("*.webm"))) if (d / "webm").exists() else 0
        preview = "/plugins/pets/" + d.name + "/preview.png" if (d / "preview.png").exists() else ""
        result.append({
            "pet_id": d.name,
            "name": meta.get("name") or config.get("name") or d.name,
            "git": meta.get("git", ""),
            "webm_count": webm_count,
            "preview": preview,
            "installed_at": meta.get("installed_at"),
        })
    return result


def uninstall_pet(pet_id: str) -> dict:
    """卸载宠物（删除目录）。"""
    pid = _safe_id(pet_id)
    target = pet_dir(pid)
    if not target.exists():
        return {"ok": False, "error": "宠物不存在"}
    shutil.rmtree(target)
    return {"ok": True, "pet_id": pid}


def load_pet_config(pet_id: str) -> dict:
    """读取已安装宠物的 config.json（pools）。"""
    target = pet_dir(pet_id)
    config_path = target / "config.json"
    if not config_path.exists():
        return {}
    return _read_jsonc(config_path)


def preset_market() -> List[dict]:
    """返回预置市场清单 + 已安装标记。"""
    installed = {p["pet_id"]: p for p in list_installed_pets()}
    result = []
    for item in PRESET_MARKET:
        it = dict(item)
        it["installed"] = item["pet_id"] in installed
        if it["installed"]:
            it["installed_info"] = installed[item["pet_id"]]
        result.append(it)
    return result
