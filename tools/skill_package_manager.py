"""
技能包管理器：解析、验证、导入技能包
支持两种格式：
1. Jingent AI 标准格式（含 skill.json）
2. TRAE/Claude Skill 兼容格式（含 SKILL.md，frontmatter + 正文）
"""
import os
import io
import json
import zipfile
import re
import logging
import shutil
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# 技能包存储目录
SKILLS_DIR = Path(__file__).parent.parent / "data" / "installed_skills"
SKILLS_DIR.mkdir(parents=True, exist_ok=True)

# 支持的图标（与前端 SKILL_ICONS 对应）
SUPPORTED_ICONS = {
    "image", "document", "globe", "mail", "clipboard", "file-text",
    "pen", "sparkles", "video", "book", "target", "message-circle",
    "code", "database", "search", "chef", "map", "dumbbell",
    "heart", "moon", "default",
}

# 支持的分类
SUPPORTED_CATEGORIES = {
    "工具类", "办公效率", "文案创作", "学习成长",
    "编程开发", "生活助手", "心理健康", "其他",
}


def _validate_skill_id(skill_id: str) -> bool:
    """验证 skill_id 是否合法（只能包含字母、数字、下划线、短横线）。"""
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', skill_id))


def _parse_frontmatter(text: str) -> Dict[str, Any]:
    """解析 Markdown 文件的 YAML frontmatter。"""
    result = {"meta": {}, "body": text}
    if not text.startswith("---"):
        return result

    parts = text.split("---", 2)
    if len(parts) < 3:
        return result

    meta_text = parts[1].strip()
    result["body"] = parts[2].strip()

    # 简单解析 YAML frontmatter（支持 name: value 格式）
    for line in meta_text.split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value:
            result["meta"][key] = value

    return result


def parse_skill_zip(zip_bytes: bytes) -> Dict[str, Any]:
    """
    解析技能包 zip 文件，提取技能信息。

    Args:
        zip_bytes: zip 文件的二进制内容

    Returns:
        dict: {
            valid: bool,
            error: str (if invalid),
            skill: dict (技能信息),
            files: list (文件列表),
        }
    """
    try:
        zip_file = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        return {"valid": False, "error": "不是有效的 zip 文件"}

    try:
        file_list = zip_file.namelist()
        result = {"valid": False, "error": "", "skill": {}, "files": file_list}

        # 1. 优先查找 skill.json（Jingent AI 标准格式）
        skill_json = None
        for fname in file_list:
            if fname.endswith("skill.json") or fname.endswith("skill.json/"):
                try:
                    with zip_file.open(fname) as f:
                        skill_json = json.loads(f.read().decode("utf-8"))
                    break
                except Exception:
                    pass

        # 2. 查找 SKILL.md（TRAE/Claude Skill 兼容格式）
        skill_md_content = None
        if not skill_json:
            for fname in file_list:
                if fname.endswith("SKILL.md"):
                    try:
                        with zip_file.open(fname) as f:
                            skill_md_content = f.read().decode("utf-8")
                        break
                    except Exception:
                        pass

        # 3. 查找 prompt.md 或 system_prompt.txt
        prompt_content = None
        for fname in file_list:
            low = fname.lower()
            if low.endswith("prompt.md") or low.endswith("system_prompt.txt"):
                try:
                    with zip_file.open(fname) as f:
                        prompt_content = f.read().decode("utf-8")
                    break
                except Exception:
                    pass

        # 根据解析到的内容构建 skill 对象
        skill = {}

        if skill_json:
            # 标准格式
            skill = skill_json
        elif skill_md_content:
            # 兼容 TRAE 格式
            parsed = _parse_frontmatter(skill_md_content)
            meta = parsed["meta"]
            body = parsed["body"]
            skill = {
                "id": meta.get("name", "").lower().replace(" ", "_") or "imported_skill",
                "name": meta.get("name", "导入的技能"),
                "description": meta.get("description", ""),
                "icon": "sparkles",
                "category": "其他",
                "type": "prompt",
                "tags": [],
                "systemPrompt": body[:5000],  # 正文作为系统提示词
            }
        elif prompt_content:
            # 最简单格式
            skill = {
                "id": "imported_skill",
                "name": "导入的技能",
                "description": "",
                "icon": "sparkles",
                "category": "其他",
                "type": "prompt",
                "tags": [],
                "systemPrompt": prompt_content[:5000],
            }
        else:
            result["error"] = "未找到 skill.json、SKILL.md 或 prompt.md 文件"
            return result

        # 验证必填字段
        if not skill.get("id"):
            result["error"] = "技能缺少 id 字段"
            return result
        if not skill.get("name"):
            result["error"] = "技能缺少 name 字段"
            return result
        if not skill.get("systemPrompt") and skill.get("type", "prompt") == "prompt":
            result["error"] = "提示词类技能缺少 systemPrompt 字段"
            return result

        # 规范化字段
        skill["id"] = skill["id"].lower().replace(" ", "_")
        if not _validate_skill_id(skill["id"]):
            skill["id"] = re.sub(r'[^a-zA-Z0-9_-]', '_', skill["id"])
        if skill.get("icon") not in SUPPORTED_ICONS:
            skill["icon"] = "default"
        if skill.get("category") not in SUPPORTED_CATEGORIES:
            skill["category"] = "其他"
        skill.setdefault("type", "prompt")
        skill.setdefault("version", "1.0.0")
        skill.setdefault("author", "未知作者")
        skill.setdefault("tags", [])

        result["valid"] = True
        result["skill"] = skill
        return result

    except Exception as e:
        logger.error("解析技能包失败: %s", e)
        return {"valid": False, "error": f"解析失败: {str(e)}"}
    finally:
        zip_file.close()


def install_skill(zip_bytes: bytes) -> Dict[str, Any]:
    """
    安装技能包（解析 + 存储）。

    Returns:
        dict: {success: bool, error: str, skill: dict}
    """
    parse_result = parse_skill_zip(zip_bytes)
    if not parse_result["valid"]:
        return {"success": False, "error": parse_result["error"]}

    skill = parse_result["skill"]
    skill_id = skill["id"]
    skill_dir = SKILLS_DIR / skill_id

    # 检查是否已存在
    if skill_dir.exists():
        # 覆盖安装：先删除旧的
        try:
            shutil.rmtree(skill_dir)
        except Exception:
            pass

    # 创建目录
    skill_dir.mkdir(parents=True, exist_ok=True)

    # 解压文件
    try:
        zip_file = zipfile.ZipFile(io.BytesIO(zip_bytes))
        zip_file.extractall(skill_dir)
        zip_file.close()
    except Exception as e:
        return {"success": False, "error": f"解压失败: {str(e)}"}

    # 写入 skill.json
    try:
        with open(skill_dir / "skill.json", "w", encoding="utf-8") as f:
            json.dump(skill, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return {"success": False, "error": f"写入配置失败: {str(e)}"}

    return {"success": True, "skill": skill}


def list_installed_skills() -> List[Dict[str, Any]]:
    """列出所有已安装的自定义技能。"""
    skills = []
    if not SKILLS_DIR.exists():
        return skills

    for entry in SKILLS_DIR.iterdir():
        if entry.is_dir():
            skill_json = entry / "skill.json"
            if skill_json.exists():
                try:
                    with open(skill_json, "r", encoding="utf-8") as f:
                        skill = json.load(f)
                        skill["installed"] = True
                        skill["install_path"] = str(entry)
                        skills.append(skill)
                except Exception as e:
                    logger.warning("读取技能 %s 失败: %s", entry.name, e)
    return skills


def get_installed_skill(skill_id: str) -> Optional[Dict[str, Any]]:
    """根据 id 获取已安装技能。"""
    skill_dir = SKILLS_DIR / skill_id
    skill_json = skill_dir / "skill.json"
    if skill_json.exists():
        try:
            with open(skill_json, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def get_installed_skill_system_prompt(skill_id: str) -> Optional[str]:
    """获取已安装技能的系统提示词。"""
    skill = get_installed_skill(skill_id)
    if skill and skill.get("type", "prompt") == "prompt":
        return skill.get("systemPrompt")
    return None


def uninstall_skill(skill_id: str) -> bool:
    """卸载已安装的技能。"""
    skill_dir = SKILLS_DIR / skill_id
    if skill_dir.exists():
        try:
            shutil.rmtree(skill_dir)
            return True
        except Exception as e:
            logger.error("卸载技能 %s 失败: %s", skill_id, e)
    return False
