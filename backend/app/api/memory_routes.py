"""
记忆路由 —— 个人 AI 陪伴助手的「全局记忆 + 细节记忆」。

- 全局记忆（type=global）：用户手动维护的核心画像（如“我是谁、性格、在意什么”）
- 细节记忆（type=detail）：对话后由 LLM 自动抽取的稳定事实/偏好/情绪状态

注入发生在 chat_routes（对话前拼进 system prompt）；
本模块只负责存取与抽取。
"""
import json
import logging
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db, Memory
from app.core.token_utils import verify_token

logger = logging.getLogger(__name__)
router = APIRouter()

# 抽取提示词：只提取“关于用户本人”的稳定信息（docs 模块1 Schema）
EXTRACT_PROMPT = (
    "你是记忆提取器。从下面的对话里提取值得长期记住的事实、偏好、人设细节。\n"
    "过滤临时一次性内容：禁止提取临时问答、单次任务结果、转瞬即逝的闲聊。\n"
    "对每条信息用一句话客观概括，不要出现『用户说/表示』等转述词；\n"
    "事件类记忆要结合时间一起存储（例：2025年10月开始在深圳实习），但不要刻意，允许记忆模糊。\n"
    "tag 只能三选一：个人信息、喜好偏好、其他。\n"
    "判断是否和已有记忆重复，动作只能是：ADD / UPDATE / SKIP。\n"
    "只输出 JSON 数组，不要多余文字：\n"
    '[{"content": "一句话事实", "tag": "个人信息|喜好偏好|其他", "action": "ADD|UPDATE|SKIP"}]'
)


class MemoryCreate(BaseModel):
    type: str = "detail"          # global | detail
    content: str
    category: Optional[str] = None
    source: str = "manual"
    character_id: Optional[str] = None  # 角色 ID；缺省用当前绑定角色


class ExtractRequest(BaseModel):
    user_message: str
    ai_reply: str


class LLMTestRequest(BaseModel):
    base_url: str
    model: str
    api_key: str


def _parse_json_array(text: str) -> List[dict]:
    """从 LLM 输出中解析 JSON 数组，兼容 ```json 代码块包裹。"""
    if not text:
        return []
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.S)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
    except json.JSONDecodeError:
        # 尝试截取第一个 [ 到最后一个 ]
        start, end = text.find("["), text.rfind("]")
        if start != -1 and end > start:
            try:
                data = json.loads(text[start:end + 1])
                if isinstance(data, list):
                    return [d for d in data if isinstance(d, dict)]
            except json.JSONDecodeError:
                pass
    logger.warning("[memory] 抽取结果解析失败，原文前 200 字: %s", text[:200])
    return []


def _init_extract_llm(base_url: str, model: str, api_key: str):
    from langchain.chat_models import init_chat_model
    from app.api.chat_routes import normalize_base_url
    return init_chat_model(
        model=model or "deepseek-chat",
        model_provider="openai",
        base_url=normalize_base_url(base_url),
        api_key=api_key,
        temperature=0,
    )


def extract_facts_from_history_sync(
        history_text: str,
        base_url: str,
        model: str,
        api_key: str,
) -> List[dict]:
    """从完整对话历史里同步抽取事实（供后台任务/手动端点复用）。

    history_text：多轮对话拼接文本（含角色标注）。
    """
    try:
        llm = _init_extract_llm(base_url, model, api_key)
        resp = llm.invoke(
            [
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": history_text},
            ]
        )
        facts = _parse_json_array(getattr(resp, "content", "") or "")
        # 归一化：兼容 tag/category 两种字段，动作 SKIP 的丢弃
        normalized = []
        for f in facts:
            content = (f.get("content") or "").strip()
            if not content:
                continue
            action = (f.get("action") or "ADD").upper()
            if action == "SKIP":
                continue
            tag = f.get("tag") or f.get("category") or "其他"
            normalized.append({"content": content, "category": tag[:30], "action": action})
        return normalized
    except Exception as e:
        logger.warning("[memory] 抽取失败: %s", e)
        return []


def extract_facts_sync(
        user_message: str,
        ai_reply: str,
        base_url: str,
        model: str,
        api_key: str,
) -> List[dict]:
    """同步抽取一条对话里的用户事实（供手动端点复用）。"""
    return extract_facts_from_history_sync(
        f"用户：{user_message}\n\nAI：{ai_reply}",
        base_url, model, api_key,
    )


def _resolve_character_id(user_id: int, explicit_cid: Optional[str] = None) -> str:
    """解析记忆归属角色：显式传入优先，否则用用户当前绑定角色，最后回退默认女仆。"""
    if explicit_cid:
        return explicit_cid
    try:
        from app.core import characters as charsvc
        return charsvc.get_current_character_id(user_id)
    except Exception:
        return "maid"


def save_extracted_facts(db: Session, user_id: int, facts: List[dict], character_id: Optional[str] = None) -> int:
    """把抽取到的事实入库（embedding 相似度去重 + 精确去重，按角色隔离），返回新增条数。

    去重策略（docs/memory-system-design.md 模块1）：
    1. 先按 content 精确匹配去重（零成本）
    2. 再用 embedding 余弦相似度 > 0.85 判定重复，跳过新增
    """
    from app.core import memory_engine as me
    cid = _resolve_character_id(user_id, character_id)
    added = 0
    for fact in facts:
        content = (fact.get("content") or "").strip()
        if not content or len(content) > 500:
            continue
        # 精确去重
        exists = (
            db.query(Memory)
            .filter(Memory.user_id == user_id, Memory.character_id == cid,
                    Memory.type == "detail", Memory.content == content)
            .first()
        )
        if exists:
            continue
        # embedding 相似度去重（后台线程内同步算，不影响流式回复）
        vec = me.embed_text(content)
        if vec and me.find_duplicate(db, user_id, cid, vec):
            logger.info("[memory] 相似记忆已存在，跳过: %s", content[:40])
            continue
        # importance：抽取的事实默认 0.5；含强烈个人标识（姓名/职业/目标）可略高
        importance = 0.5
        cat = (fact.get("category") or "其他")[:30]
        if cat in ("个人信息", "目标计划", "重要事件"):
            importance = 0.7
        db.add(Memory(
            user_id=user_id,
            type="detail",
            category=cat,
            content=content,
            source="extract",
            character_id=cid,
            importance=importance,
            weight=1.0,
            access_count=0,
            embedding=me.encode_embedding(vec),
        ))
        added += 1
    db.commit()
    return added


# ==================================================================
# 端点
# ==================================================================

@router.get("/ai/memories", summary="获取我的记忆（全局 + 细节，按角色隔离）")
def list_memories(
        user_id: int = Depends(verify_token),
        type: Optional[str] = Query(None, pattern="^(global|detail)$"),
        character_id: Optional[str] = Query(None, description="角色 ID；缺省用当前绑定角色"),
        limit: int = Query(50, ge=1, le=200),
        db: Session = Depends(get_db),
):
    cid = _resolve_character_id(user_id, character_id)
    q = db.query(Memory).filter(Memory.user_id == user_id)
    if type == "global":
        # 全局画像跨角色共享（不按 character_id 过滤）
        q = q.filter(Memory.type == "global")
    elif type == "detail":
        # 细节记忆按角色隔离
        q = q.filter(Memory.type == "detail", Memory.character_id == cid)
    else:
        # 不指定 type：global 全量 + 当前角色的 detail
        from sqlalchemy import or_
        q = q.filter(or_(
            Memory.type == "global",
            (Memory.type == "detail") & (Memory.character_id == cid),
        ))
    rows = q.order_by(Memory.id.desc()).limit(limit).all()
    return {
        "code": 200,
        "data": [
            {
                "id": m.id,
                "type": m.type,
                "category": m.category,
                "content": m.content,
                "source": m.source,
                "character_id": m.character_id,
                "importance": m.importance,
                "weight": m.weight,
                "access_count": m.access_count,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in rows
        ],
    }


@router.post("/ai/memories", summary="手动添加记忆")
def create_memory(
        body: MemoryCreate,
        user_id: int = Depends(verify_token),
        db: Session = Depends(get_db),
):
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="记忆内容不能为空")
    if len(content) > 500:
        raise HTTPException(status_code=400, detail="记忆内容过长（<=500字）")
    mem_type = body.type if body.type in ("global", "detail") else "detail"
    mem = Memory(
        user_id=user_id,
        type=mem_type,
        category=(body.category or "其他")[:30] if body.category else None,
        content=content,
        source=body.source or "manual",
        # 全局画像 = 用户级（不绑定角色）；细节记忆 = 绑定当前角色
        character_id=None if mem_type == "global" else _resolve_character_id(user_id, body.character_id),
        importance=0.8 if mem_type == "global" else 0.5,
        weight=1.0,
        access_count=0,
    )
    db.add(mem)
    db.commit()
    db.refresh(mem)
    return {"code": 200, "id": mem.id}


@router.delete("/ai/memories/{mem_id}", summary="删除一条记忆")
def delete_memory(
        mem_id: int,
        user_id: int = Depends(verify_token),
        db: Session = Depends(get_db),
):
    mem = db.query(Memory).filter(Memory.id == mem_id, Memory.user_id == user_id).first()
    if not mem:
        raise HTTPException(status_code=404, detail="记忆不存在")
    db.delete(mem)
    db.commit()
    return {"code": 200, "msg": "已删除"}


@router.post("/ai/memories/extract", summary="手动触发抽取：从一段对话提取用户事实并入库")
def extract_memories(
        body: ExtractRequest,
        user_id: int = Depends(verify_token),
        db: Session = Depends(get_db),
):
    from app.config import MODEL, DASHSCOPE_URL, DASHSCOPE_API_KEY
    facts = extract_facts_sync(
        body.user_message, body.ai_reply,
        DASHSCOPE_URL, MODEL, DASHSCOPE_API_KEY,
    )
    added = save_extracted_facts(db, user_id, facts)
    return {"code": 200, "extracted": facts, "added": added}


@router.post("/ai/llm/test", summary="测试用户自定义的 LLM 配置连通性")
def test_llm_config(body: LLMTestRequest):
    from langchain.chat_models import init_chat_model
    from app.api.chat_routes import normalize_base_url
    if not body.api_key:
        raise HTTPException(status_code=400, detail="API Key 不能为空")
    try:
        llm = init_chat_model(
            model=body.model or "deepseek-chat",
            model_provider="openai",
            base_url=normalize_base_url(body.base_url),
            api_key=body.api_key,
            temperature=0,
            max_tokens=16,
        )
        resp = llm.invoke("请只回复四个字：连接成功")
        return {"code": 200, "msg": "连接成功", "reply": str(getattr(resp, "content", "")).strip()[:50]}
    except Exception as e:
        logger.warning("[llm/test] 连接失败: %s", e)
        raise HTTPException(status_code=502, detail=f"连接失败：{str(e)[:200]}")
