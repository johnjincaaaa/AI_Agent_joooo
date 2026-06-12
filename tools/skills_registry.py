"""
技能注册表：集中管理可被前端选择的 LLM 工具链（不含智能联网）。
新增技能时在此追加条目即可。
"""
from typing import List

from .tool_Image_parsing import image_analyze

SKILL_REGISTRY = {
    "image_parsing": {
        "id": "image_parsing",
        "name": "图片解析",
        "description": "分析图片内容、尺寸、格式等属性",
        "icon": "image",
        "tools": [image_analyze],
    },
}


def get_skill_catalog():
    """返回前端展示用的技能列表（不含工具对象）。"""
    return [
        {
            "id": skill["id"],
            "name": skill["name"],
            "description": skill["description"],
            "icon": skill["icon"],
        }
        for skill in SKILL_REGISTRY.values()
    ]


def resolve_tools(enabled_skill_ids: List[str]):
    """根据前端选中的技能 id 解析 LangChain 工具列表。"""
    tools = []
    seen = set()
    for skill_id in enabled_skill_ids:
        skill = SKILL_REGISTRY.get(skill_id)
        if not skill:
            continue
        for tool in skill["tools"]:
            tool_name = getattr(tool, "name", None) or str(tool)
            if tool_name not in seen:
                seen.add(tool_name)
                tools.append(tool)
    return tools
