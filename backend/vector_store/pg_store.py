"""
向量存储层 —— pgvector 实现

Public API：
  embed_texts / embed_query
  add_documents
  query_documents
  get_collection_stats
  delete_collection
  is_semantic_duplicate
"""
from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from sqlalchemy import delete as sa_delete, func

from config import get_settings
from db.database import SessionLocal
from db.models import ArticleChunk

logger = logging.getLogger(__name__)
settings = get_settings()

_embeddings: Embeddings | None = None
_embeddings_cache_identity: tuple | None = None

_CHUNK_SIZE    = 500   # characters per chunk (≈ 300–500 tokens for Chinese)
_CHUNK_OVERLAP = 50    # overlap between consecutive chunks
_SENTENCE_ENDS = ("。", "！", "？", "…", "\n", ". ", "! ", "? ")


def _resolve_embedding_device() -> str:
    d = settings.embedding_device
    if d in ("cpu", "mps", "cuda"):
        return d
    import torch
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _embedding_implementation_identity() -> tuple:
    """embedding 实现的配置指纹；任一变化则换新客户端。"""
    s = settings
    route = (
        (s.ark_sdk_base_url or "default_sdk")
        if s.embedding_provider == "ark"
        else s.embeddings_base_url
    )
    return (
        s.embedding_provider,
        s.embedding_model,
        route,
        s.ark_embedding_dimensions,
    )


def _drop_embeddings_cache() -> None:
    global _embeddings
    emb = _embeddings
    _embeddings = None
    closer = getattr(emb, "close", None)
    if callable(closer):
        try:
            closer()
        except Exception:
            pass


def _get_embeddings() -> Embeddings:
    global _embeddings, _embeddings_cache_identity
    ident = _embedding_implementation_identity()

    if _embeddings is not None:
        if ident == _embeddings_cache_identity:
            return _embeddings
        logger.info(
            "Embedding config fingerprint changed (%s → %s), rebuilding client",
            _embeddings_cache_identity,
            ident,
        )
        _drop_embeddings_cache()

    if settings.embedding_provider == "local":
        import os
        from langchain_huggingface import HuggingFaceEmbeddings

        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        os.environ.setdefault("HF_DATASETS_OFFLINE", "1")

        device = _resolve_embedding_device()
        logger.info(
            "Using local HuggingFace embeddings model=%s device=%s",
            settings.embedding_model,
            device,
        )
        _embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": device},
            encode_kwargs={"normalize_embeddings": True},
        )
    elif settings.embedding_provider == "ark":
        from vector_store.ark_multimodal_embeddings import ArkMultimodalEmbeddings

        api_key = settings.ark_embedding_api_key
        if not api_key:
            raise RuntimeError(
                "EMBEDDING_PROVIDER=ark requires OPENAI_API_KEY or ARK_API_KEY"
            )
        base = settings.ark_sdk_base_url
        logger.info(
            "Using Ark SDK multimodal embeddings model=%s dims=%s base_url=%s",
            settings.embedding_model,
            settings.ark_embedding_dimensions,
            base or "(SDK default)",
        )
        _embeddings = ArkMultimodalEmbeddings(
            api_key=api_key,
            model=settings.embedding_model,
            dimensions=settings.ark_embedding_dimensions,
            base_url=base,
        )
    else:
        kwargs: dict = {
            "model": settings.embedding_model,
            "api_key": settings.openai_api_key,
        }
        if settings.embeddings_base_url:
            kwargs["base_url"] = settings.embeddings_base_url
        _embeddings = OpenAIEmbeddings(**kwargs)

    _embeddings_cache_identity = ident
    return _embeddings


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks, preferring sentence boundaries."""
    if len(text) <= _CHUNK_SIZE:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + _CHUNK_SIZE, len(text))
        if end < len(text):
            best = end
            for i in range(end, max(end - 50, start), -1):
                if text[i - 1] in _SENTENCE_ENDS:
                    best = i
                    break
            end = best
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = end - _CHUNK_OVERLAP
    return [c for c in chunks if c]


# ── Public helpers ─────────────────────────────────────────────────────────────

def embed_texts(texts: List[str]) -> List[List[float]]:
    return _get_embeddings().embed_documents(texts)


def embed_query(text: str) -> List[float]:
    return _get_embeddings().embed_query(text)


# ── Write ──────────────────────────────────────────────────────────────────────

def add_documents(
    source_id: str,
    doc_ids: List[str],
    texts: List[str],
    metadatas: List[dict],
) -> int:
    """Chunk, embed and upsert documents into pgvector. Returns count of articles added."""
    chunk_rows: list[dict] = []
    articles_added = 0

    for doc_id, text, meta in zip(doc_ids, texts, metadatas):
        chunks = _chunk_text(text)
        for i, chunk in enumerate(chunks):
            chunk_rows.append({
                "chunk_id":     f"{doc_id}_c{i}",
                "article_id":   doc_id,
                "source_id":    source_id,
                "content":      chunk,
                "chunk_index":  i,
                "chunk_total":  len(chunks),
                "author":       meta.get("author", ""),
                "url":          meta.get("url", ""),
                "published_date": meta.get("published_date", ""),
                "article_type": meta.get("article_type", ""),
            })
        articles_added += 1

    if not chunk_rows:
        return 0

    embeddings = embed_texts([r["content"] for r in chunk_rows])

    db = SessionLocal()
    try:
        for row, emb in zip(chunk_rows, embeddings):
            existing = (
                db.query(ArticleChunk)
                .filter(ArticleChunk.chunk_id == row["chunk_id"])
                .first()
            )
            if existing:
                existing.embedding = emb
            else:
                db.add(ArticleChunk(id=str(uuid.uuid4()), embedding=emb, **row))
        db.commit()
        logger.info(
            "Upserted %d chunks (%d articles) for source %s",
            len(chunk_rows), articles_added, source_id,
        )
    finally:
        db.close()

    return articles_added


# ── Read ───────────────────────────────────────────────────────────────────────

def query_documents(
    source_ids: List[str],
    query_text: str,
    n_results: int = 5,
    where: Optional[dict] = None,
) -> List[dict]:
    """
    Query pgvector using cosine similarity across one or multiple sources.

    `where` accepts a filter dict, e.g.:
        {"published_date": {"$eq": "2026-05-18"}}
    """
    query_vec = embed_query(query_text)

    date_filter: str | None = None
    if where:
        pf = where.get("published_date", {})
        if isinstance(pf, dict):
            date_filter = pf.get("$eq")

    db = SessionLocal()
    try:
        dist = ArticleChunk.embedding.cosine_distance(query_vec)
        q = db.query(ArticleChunk, (1 - dist).label("score"))
        if source_ids:
            q = q.filter(ArticleChunk.source_id.in_(source_ids))
        if date_filter:
            q = q.filter(ArticleChunk.published_date == date_filter)
        rows = q.order_by(dist).limit(n_results).all()

        return [
            {
                "content": chunk.content,
                "metadata": {
                    "source_id":      chunk.source_id,
                    "author":         chunk.author,
                    "url":            chunk.url,
                    "published_date": chunk.published_date,
                    "article_type":   chunk.article_type,
                    "chunk_index":    chunk.chunk_index,
                    "chunk_total":    chunk.chunk_total,
                },
                "score":     round(float(score), 4),
                "source_id": chunk.source_id,
            }
            for chunk, score in rows
        ]
    finally:
        db.close()


def get_collection_stats(source_id: str) -> dict:
    db = SessionLocal()
    try:
        count = (
            db.query(func.count(ArticleChunk.id))
            .filter(ArticleChunk.source_id == source_id)
            .scalar()
        )
        return {"source_id": source_id, "document_count": count or 0}
    finally:
        db.close()


def delete_collection(source_id: str) -> None:
    db = SessionLocal()
    try:
        db.execute(sa_delete(ArticleChunk).where(ArticleChunk.source_id == source_id))
        db.commit()
        logger.info("Deleted vectors for source: %s", source_id)
    except Exception as e:
        logger.warning("Failed to delete vectors for source %s: %s", source_id, e)
        db.rollback()
    finally:
        db.close()


def is_semantic_duplicate(
    source_id: str,
    text: str,
    threshold: float = 0.95,
) -> bool:
    """Return True if the text is semantically too similar to existing documents."""
    query_vec = embed_query(text)
    db = SessionLocal()
    try:
        dist = ArticleChunk.embedding.cosine_distance(query_vec)
        row = (
            db.query((1 - dist).label("score"))
            .filter(ArticleChunk.source_id == source_id)
            .order_by(dist)
            .first()
        )
        if row is None:
            return False
        return float(row.score) >= threshold
    finally:
        db.close()
