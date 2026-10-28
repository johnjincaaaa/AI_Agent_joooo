"""
RAG 向量库 —— 主对话消息语义检索。

- embedding：默认 Ollama bge-m3（本地，1024 维，中文友好，隐私不外发）
  - 也可配置为 OpenAI 兼容的 embedding 服务（见 settings.EMBEDDING_*）
- 向量存储：chromadb（持久化到 ops/data/vector_db）
- 用途：主对话（chat_type=main）消息入向量库，支持语义检索历史对话

设计：
  - 只在主对话写入向量；新建会话（secondary）不写入
  - 检索：给定 query，返回最相关的历史消息片段
"""
import json
import logging
import threading
from pathlib import Path
from typing import List, Optional

import requests

from app.config.settings import (
    EMBEDDING_BASE_URL,
    EMBEDDING_MODEL,
    EMBEDDING_API_KEY,
    EMBEDDING_DIM,
)
from app.core.paths import data_dir

logger = logging.getLogger(__name__)

# ── 配置 ──────────────────────────────────────────────
# 从 .env 读取（settings.py 已解析，见 EMBEDDING_* 常量）
_VECTOR_DIR = data_dir() / "vector_db"
_VECTOR_DIR.mkdir(parents=True, exist_ok=True)


def _embed_texts(texts: List[str], embedding_cfg: Optional[dict] = None) -> List[List[float]]:
    """把文本批量转成向量。

    embedding_cfg：可选 {base_url, model, api_key}，覆盖 .env 全局配置。

    协议自适应：
      - OpenAI 兼容：POST {base}/embeddings（或已含 /v1），带 Bearer Key，
        返回 {"data": [{"embedding": [...]}]}
      - Ollama 原生：POST {base}/api/embeddings，返回 {"embedding": [...]}
    """
    cfg = embedding_cfg or {}
    base = (cfg.get("base_url") or EMBEDDING_BASE_URL).rstrip("/")
    model = cfg.get("model") or EMBEDDING_MODEL
    api_key = cfg.get("api_key") or EMBEDDING_API_KEY
    # 带 API Key，或地址显式含 /v1，视为 OpenAI 兼容
    is_openai = bool(api_key) or ("/v1" in base)

    embeddings = []
    for text in texts:
        try:
            if is_openai:
                url = base + ("/embeddings" if not base.endswith("/embeddings") else "")
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                resp = requests.post(
                    url,
                    headers=headers,
                    json={"model": model, "input": text},
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                emb = (data.get("data") or [{}])[0].get("embedding")
            else:
                resp = requests.post(
                    f"{base}/api/embeddings",
                    json={"model": model, "prompt": text},
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                emb = data.get("embedding")
            embeddings.append(emb if emb else [0.0] * EMBEDDING_DIM)
        except Exception as e:
            logger.warning("[rag] embedding 失败: %s", e)
            embeddings.append([0.0] * EMBEDDING_DIM)
    return embeddings


class RAGStore:
    """主对话消息向量库（懒加载 chromadb）。"""

    def __init__(self) -> None:
        self._client = None
        self._collection = None
        self._lock = threading.Lock()

    def _ensure(self):
        if self._collection is not None:
            return
        with self._lock:
            if self._collection is not None:
                return
            import chromadb
            self._client = chromadb.PersistentClient(path=str(_VECTOR_DIR))
            # 每个用户一个 collection？还是全局一个？用 metadata 区分 user_id
            # 全局一个 collection，metadata 带 user_id，检索时 where 过滤
            self._collection = self._client.get_or_create_collection(
                name="main_chat_messages",
                metadata={"hnsw:space": "cosine"},
            )

    def add_message(self, user_id: int, message_id: int, content: str) -> None:
        """把一条主对话消息写入向量库。"""
        if not content or not content.strip():
            return
        self._ensure()
        try:
            emb = _embed_texts([content])[0]
            self._collection.upsert(
                ids=[f"msg_{message_id}"],
                embeddings=[emb],
                documents=[content[:2000]],  # 截断超长内容
                metadatas=[{"user_id": user_id}],
            )
        except Exception as e:
            logger.warning("[rag] 写入向量失败 msg=%s: %s", message_id, e)

    def search(self, user_id: int, query: str, k: int = 5, embedding_cfg: Optional[dict] = None) -> List[str]:
        """语义检索主对话历史，返回相关消息文本列表。

        embedding_cfg：可选 {base_url, model, api_key}，用户前端自定义向量模型；
        不传则用 .env 全局配置。仅影响本次 query 的向量化。
        """
        if not query or not query.strip():
            return []
        self._ensure()
        try:
            emb = _embed_texts([query], embedding_cfg)[0]
            results = self._collection.query(
                query_embeddings=[emb],
                n_results=k,
                where={"user_id": user_id},
            )
            docs = results.get("documents") or [[]]
            return [d for d in docs[0] if d]
        except Exception as e:
            logger.warning("[rag] 检索失败: %s", e)
            return []


# 全局单例
_rag_store: Optional[RAGStore] = None


def get_rag_store() -> RAGStore:
    global _rag_store
    if _rag_store is None:
        _rag_store = RAGStore()
    return _rag_store
