from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

import chromadb
from chromadb import Collection
from chromadb.config import Settings as ChromaSettings
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

_client: chromadb.PersistentClient | None = None
_embeddings: Embeddings | None = None


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        persist_dir = Path(settings.chroma_persist_dir)
        persist_dir.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


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


def _get_embeddings() -> Embeddings:
    global _embeddings
    if _embeddings is None:
        if settings.embedding_provider == "local":
            import os
            from langchain_huggingface import HuggingFaceEmbeddings

            # Avoid slow startup network check for model updates
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
        else:
            kwargs: dict = {
                "model": settings.embedding_model,
                "api_key": settings.openai_api_key,
            }
            if settings.openai_base_url:
                kwargs["base_url"] = settings.openai_base_url
            _embeddings = OpenAIEmbeddings(**kwargs)
    return _embeddings


_CHUNK_SIZE    = 500   # characters per chunk (≈ 300-500 tokens for Chinese)
_CHUNK_OVERLAP = 50    # overlap between consecutive chunks
_SENTENCE_ENDS = ("。", "！", "？", "…", "\n", ". ", "! ", "? ")


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks, preferring sentence boundaries."""
    if len(text) <= _CHUNK_SIZE:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + _CHUNK_SIZE, len(text))
        # Try to extend to a sentence boundary within a 50-char window
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


def _collection_name(source_id: str) -> str:
    return f"source_{source_id}"


def get_or_create_collection(source_id: str) -> Collection:
    client = _get_client()
    name = _collection_name(source_id)
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def delete_collection(source_id: str) -> None:
    client = _get_client()
    name = _collection_name(source_id)
    try:
        client.delete_collection(name)
        logger.info("Deleted collection: %s", name)
    except Exception:
        pass


def embed_texts(texts: List[str]) -> List[List[float]]:
    return _get_embeddings().embed_documents(texts)


def embed_query(text: str) -> List[float]:
    return _get_embeddings().embed_query(text)


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def is_semantic_duplicate(
    source_id: str,
    text: str,
    threshold: float = 0.95,
) -> bool:
    """Return True if the text is semantically too similar to existing documents."""
    collection = get_or_create_collection(source_id)
    if collection.count() == 0:
        return False
    query_vec = embed_query(text)
    results = collection.query(
        query_embeddings=[query_vec],
        n_results=1,
        include=["distances"],
    )
    distances = results.get("distances", [[]])[0]
    if not distances:
        return False
    # Chroma cosine distance = 1 - similarity
    similarity = 1.0 - distances[0]
    return similarity >= threshold


def add_documents(
    source_id: str,
    doc_ids: List[str],
    texts: List[str],
    metadatas: List[dict],
) -> int:
    """Chunk, embed and store documents. Returns count of articles added."""
    collection = get_or_create_collection(source_id)

    chunk_ids, chunk_texts, chunk_metas = [], [], []
    articles_added = 0

    for doc_id, text, meta in zip(doc_ids, texts, metadatas):
        chunks = _chunk_text(text)
        for i, chunk in enumerate(chunks):
            chunk_ids.append(f"{doc_id}_c{i}")
            chunk_texts.append(chunk)
            chunk_metas.append({**meta, "chunk_index": i, "chunk_total": len(chunks)})
        articles_added += 1

    if not chunk_ids:
        return 0

    embeddings = embed_texts(chunk_texts)
    collection.add(
        ids=chunk_ids,
        embeddings=embeddings,
        documents=chunk_texts,
        metadatas=chunk_metas,
    )
    logger.info(
        "Added %d chunks (%d articles) to collection source_%s",
        len(chunk_ids), articles_added, source_id,
    )
    return articles_added


def query_documents(
    source_ids: List[str],
    query_text: str,
    n_results: int = 5,
    where: Optional[dict] = None,
) -> List[dict]:
    """Query across one or multiple collections and merge results."""
    query_vec = embed_query(query_text)
    all_results: list[dict] = []

    for source_id in source_ids:
        collection = get_or_create_collection(source_id)
        if collection.count() == 0:
            continue
        try:
            res = collection.query(
                query_embeddings=[query_vec],
                n_results=min(n_results, collection.count()),
                include=["documents", "metadatas", "distances"],
                where=where,
            )
            docs = res.get("documents", [[]])[0]
            metas = res.get("metadatas", [[]])[0]
            dists = res.get("distances", [[]])[0]
            for doc, meta, dist in zip(docs, metas, dists):
                all_results.append(
                    {
                        "content": doc,
                        "metadata": meta,
                        "score": round(1.0 - dist, 4),
                        "source_id": source_id,
                    }
                )
        except Exception as e:
            logger.warning("Query failed for source %s: %s", source_id, e)

    all_results.sort(key=lambda x: x["score"], reverse=True)
    return all_results[:n_results]


def get_collection_stats(source_id: str) -> dict:
    collection = get_or_create_collection(source_id)
    return {"source_id": source_id, "document_count": collection.count()}
