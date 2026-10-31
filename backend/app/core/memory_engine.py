"""
记忆引擎 —— 细节记忆的 embedding 去重、语义召回、遗忘曲线。

依赖（docs/memory-system-design.md）：
- embedding：复用 app.core.rag._embed_texts（Ollama bge-m3，1024 维）
- 去重：余弦相似度 > 阈值(0.85) 判定重复 → 跳过新增（防记忆爆炸）
- 召回：query embedding 与全部细节记忆 embedding 算余弦，top-K（默认 5）
- 遗忘曲线：Recency-Importance-Relevance 评分 + 半衰期衰减

不依赖 chromadb：embedding 以 JSON 数组存 Memory.embedding 列，
召回时用纯 Python 余弦相似度（1024 维 × 数十条记忆，毫秒级）。
"""
import json
import logging
import math
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ── 可调参数 ──────────────────────────────────────────
DUPLICATE_THRESHOLD = 0.85   # 余弦相似度阈值，超过判定重复
RECALL_TOP_K = 5             # 语义召回条数（文档建议 3~6）
HALF_LIFE_DAYS = 30.0        # 半衰期：30 天没人召回，权重减半
RECALL_BONUS = 0.1           # 每被召回一次，热度 +10%
IMPORTANCE_SCALE = 1.5       # importance 映射到 [0.5, 1.5] 的缩放


def _cosine(a: List[float], b: List[float]) -> float:
    """余弦相似度（纯 Python，1024 维毫秒级）。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def embed_text(text: str) -> List[float]:
    """把文本转成 embedding（复用 rag 的 bge-m3 向量化）。失败返回空列表。"""
    if not text or not text.strip():
        return []
    try:
        from app.core.rag import _embed_texts
        return _embed_texts([text])[0]
    except Exception as e:
        logger.warning("[memory-engine] embedding 失败: %s", e)
        return []


def encode_embedding(vec: List[float]) -> Optional[str]:
    """向量转 JSON 字符串存储。"""
    if not vec:
        return None
    return json.dumps(vec, separators=(",", ":"))


def decode_embedding(raw: Optional[str]) -> List[float]:
    """JSON 字符串转向量。"""
    if not raw:
        return []
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


# ── 去重 ──────────────────────────────────────────────

def find_duplicate(db: Session, user_id: int, cid: str, new_vec: List[float],
                   threshold: float = DUPLICATE_THRESHOLD) -> Optional["Memory"]:
    """在该用户该角色的细节记忆里找与新向量最相似的一条；超过阈值返回它，否则 None。"""
    if not new_vec:
        return None
    from app.core.db import Memory
    rows = (
        db.query(Memory)
        .filter(Memory.user_id == user_id, Memory.character_id == cid,
                Memory.type == "detail")
        .all()
    )
    best = None
    best_sim = 0.0
    for m in rows:
        old_vec = decode_embedding(m.embedding)
        if not old_vec:
            continue
        sim = _cosine(new_vec, old_vec)
        if sim > best_sim:
            best_sim = sim
            best = m
    if best is not None and best_sim >= threshold:
        return best
    return None


# ── 遗忘曲线 / 权重 ───────────────────────────────────

def _recency_decay(m: "Memory", now: datetime) -> float:
    """半衰期衰减：距上次召回（或创建）越久，衰减越强。0~1。"""
    anchor = m.last_recalled_at or m.created_at or now
    if anchor.tzinfo is not None:
        anchor = anchor.replace(tzinfo=None)
    age_days = max(0.0, (now - anchor).total_seconds() / 86400.0)
    return 0.5 ** (age_days / HALF_LIFE_DAYS)


def _importance_factor(importance: Optional[float]) -> float:
    """importance(0~1) 映射到 [0.5, 1.5]，高重要度更靠前。"""
    if importance is None:
        importance = 0.5
    importance = max(0.0, min(1.0, importance))
    return 0.5 + importance * (IMPORTANCE_SCALE - 0.5)


def _recall_factor(access_count: Optional[int]) -> float:
    """召回热度：被召回越多越不容易忘。1 + 0.1 * count。"""
    return 1.0 + RECALL_BONUS * max(0, access_count or 0)


def current_weight(m: "Memory", now: Optional[datetime] = None) -> float:
    """综合权重（Recency-Importance-Relevance 中的 RI 部分，Relevance 由召回时算）。

    weight = importance_factor * recency_decay * recall_factor
    """
    now = now or datetime.now()
    return _importance_factor(m.importance) * _recency_decay(m, now) * _recall_factor(m.access_count)


# ── 语义召回 ──────────────────────────────────────────

def recall_details(db: Session, user_id: int, cid: str, query: str,
                   k: int = RECALL_TOP_K, now: Optional[datetime] = None
                   ) -> Tuple[List[dict], Optional[str]]:
    """语义召回该用户该角色的细节记忆。

    返回 (memory_dicts, query_embedding_json)。
    memory_dicts 已按「相似度 × 权重」重排，附 relevance/weight 供前端可视化。

    若无可用 embedding（embedding 服务不可用），降级为「按权重取最近 k 条」。
    """
    from app.core.db import Memory
    now = now or datetime.now()
    rows = (
        db.query(Memory)
        .filter(Memory.user_id == user_id, Memory.character_id == cid,
                Memory.type == "detail")
        .all()
    )
    if not rows:
        return [], None

    qvec = embed_text(query)
    qvec_json = encode_embedding(qvec)

    # 有 query embedding 且记忆有 embedding → 语义召回
    if qvec:
        scored = []
        for m in rows:
            mv = decode_embedding(m.embedding)
            sim = _cosine(qvec, mv) if mv else 0.0
            w = current_weight(m, now)
            scored.append((m, sim, sim * w))
        # 按最终得分排序，取 top-k；sim>0 的优先（语义相关）
        scored.sort(key=lambda t: t[2], reverse=True)
        top = scored[:k]
        return [_to_dict(m, sim, w) for m, sim, w in top], qvec_json

    # 降级：无 embedding，按权重排序取最近 k 条
    ranked = sorted(rows, key=lambda m: current_weight(m, now), reverse=True)[:k]
    return [_to_dict(m, 0.0, current_weight(m, now)) for m in ranked], qvec_json


def _to_dict(m: "Memory", similarity: float, weight: float) -> dict:
    return {
        "id": m.id,
        "content": m.content,
        "category": m.category,
        "similarity": round(similarity, 4),
        "weight": round(weight, 4),
        "importance": m.importance,
        "access_count": m.access_count or 0,
    }


def mark_recalled(db: Session, mem_ids: List[int], now: Optional[datetime] = None) -> None:
    """召回后更新 access_count 与 last_recalled_at，并重算 weight 持久化。"""
    if not mem_ids:
        return
    from app.core.db import Memory
    now = now or datetime.now()
    rows = db.query(Memory).filter(Memory.id.in_(mem_ids)).all()
    for m in rows:
        m.access_count = (m.access_count or 0) + 1
        m.last_recalled_at = now
        m.weight = current_weight(m, now)
    db.commit()
