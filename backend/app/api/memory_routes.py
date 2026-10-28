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

# 抽取提示词：只提取“关于用户本人”的稳定信息
EXTRACT_PROMPT = (
    "你是记忆提取器。从下面的对话中，提取关于【用户本人】的值得长期记住的稳定信息。\n"
    "提取范围：个人信息（姓名/职业/所在地等）、长期喜好与偏好、习惯、目标与计划、"
    "情绪状态、重要生活事件。\n"
    "不提取：一次性寒暄、临时请求、AI 的自我介绍、明显冲突的临时情绪。\n"
    "对每条信息用一句话概括，客观陈述，不要出现『用户说/表示』等转述词。\n"
    "只输出 JSON 数组，不要多余文字：\n"
    '[{"content": "一句话事实", "category": "个人信息|喜好偏好|目标计划|情绪状态|重要事件|其他"}]'
)


class MemoryCreate(BaseModel):
    type: str = "detail"          # global | detail
    content: str
    category: Optional[str] = None
    source: str = "manual"


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


def extract_facts_sync(
        user_message: str,
        ai_reply: str,
        base_url: str,
        model: str,
        api_key: str,
) -> List[dict]:
    """同步抽取一条对话里的用户事实（供后台任务/手动端点复用）。"""
    try:
        llm = _init_extract_llm(base_url, model, api_key)
        resp = llm.invoke(
            [
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": f"用户：{user_message}\n\nAI：{ai_reply}"},
            ]
        )
        return _parse_json_array(getattr(resp, "content", "") or "")
    except Exception as e:
        logger.warning("[memory] 抽取失败: %s", e)
        return []


def save_extracted_facts(db: Session, user_id: int, facts: List[dict]) -> int:
    """把抽取到的事实入库（content 去重），返回新增条数。"""
    added = 0
    for fact in facts:
        content = (fact.get("content") or "").strip()
        if not content or len(content) > 500:
            continue
        exists = (
            db.query(Memory)
            .filter(Memory.user_id == user_id, Memory.type == "detail", Memory.content == content)
            .first()
        )
        if exists:
            continue
        db.add(Memory(
            user_id=user_id,
            type="detail",
            category=(fact.get("category") or "其他")[:30],
            content=content,
            source="extract",
        ))
        added += 1
    db.commit()
    return added


# ==================================================================
# 端点
# ==================================================================

@router.get("/ai/memories", summary="获取我的记忆（全局 + 细节）")
def list_memories(
        user_id: int = Depends(verify_token),
        type: Optional[str] = Query(None, pattern="^(global|detail)$"),
        limit: int = Query(50, ge=1, le=200),
        db: Session = Depends(get_db),
):
    q = db.query(Memory).filter(Memory.user_id == user_id)
    if type:
        q = q.filter(Memory.type == type)
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
    mem = Memory(
        user_id=user_id,
        type=body.type if body.type in ("global", "detail") else "detail",
        category=(body.category or "其他")[:30] if body.category else None,
        content=content,
        source=body.source or "manual",
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
