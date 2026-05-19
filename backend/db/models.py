from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base

EMBEDDING_DIM = 1024  # bge-m3 / Ark doubao 多模态默认 dimensions=1024 须与向量列一致


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Source(Base):
    """RSS / 公众号数据源配置"""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "rss"
    handle: Mapped[str] = mapped_column(String(500), nullable=False)      # RSS Feed URL
    description: Mapped[str] = mapped_column(Text, default="")
    content_type: Mapped[str] = mapped_column(String(20), default="daily")  # "daily" | "research"
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="ok")           # "ok" | "error"
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    articles: Mapped[list[RawArticle]] = relationship("RawArticle", back_populates="source", cascade="all, delete-orphan")


class RawArticle(Base):
    """原始推文 / 公众号文章"""

    __tablename__ = "raw_articles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("sources.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(String(500), default="")
    author: Mapped[str] = mapped_column(String(100), default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # SHA-256
    vectorized: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    source: Mapped[Source] = relationship("Source", back_populates="articles")


class Report(Base):
    """盘前 / 盘后 AI 简报"""

    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    report_date: Mapped[str] = mapped_column(String(10), nullable=False)   # "2024-01-15"
    report_type: Mapped[str] = mapped_column(String(10), nullable=False)   # "pre" | "post"
    sentiment_json: Mapped[str] = mapped_column(Text, default="{}")
    hotspots_json: Mapped[str] = mapped_column(Text, default="{}")
    stock_prices_json: Mapped[str] = mapped_column(Text, default="{}")
    summary_text: Mapped[str] = mapped_column(Text, default="")
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    source_digest_json: Mapped[str] = mapped_column(Text, default="[]")  # [{source_name,item_count,preview}]
    # 盘前/盘后简报生成当下计算的热门股池快照（与 /api/tickers/hot 同算法）
    hot_pool_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ChatHistory(Base):
    """前端 RAG 对话历史"""

    __tablename__ = "chat_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)          # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_ids: Mapped[str] = mapped_column(Text, default="[]")            # JSON list of source IDs
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PipelineRun(Base):
    """流水线运行日志"""

    __tablename__ = "pipeline_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=_uuid)
    run_type: Mapped[str] = mapped_column(String(20), nullable=False)  # pre|post|manual|single_sync|reembed
    status: Mapped[str] = mapped_column(String(20), default="queued")      # "queued"|"running"|"success"|"failed"
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_msg: Mapped[str] = mapped_column(Text, default="")
    articles_crawled: Mapped[int] = mapped_column(Integer, default=0)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SourceCrawlLog(Base):
    """每次 pipeline 中每个数据源的爬取任务记录"""

    __tablename__ = "source_crawl_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|running|success|failed
    articles_found: Mapped[int] = mapped_column(Integer, default=0)
    error_msg: Mapped[str] = mapped_column(Text, default="")
    steps: Mapped[str] = mapped_column(Text, default="[]")  # JSON list of {key,name,status,detail}
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TickerMention(Base):
    """历史表：早期方案曾写入提及行；热门股现改为直接扫 raw_articles 正文，此表可闲置。"""

    __tablename__ = "ticker_mentions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    article_id: Mapped[str] = mapped_column(String(36), ForeignKey("raw_articles.id", ondelete="CASCADE"), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(100), default="")
    mention_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # "2026-05-16"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ArticleChunk(Base):
    """pgvector 向量块：research 类型文章的分块嵌入，替代原有 ChromaDB 存储"""

    __tablename__ = "article_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    chunk_id: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    article_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("raw_articles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    chunk_total: Mapped[int] = mapped_column(Integer, default=1)
    author: Mapped[str] = mapped_column(String(100), default="")
    url: Mapped[str] = mapped_column(String(500), default="")
    published_date: Mapped[str] = mapped_column(String(10), default="", index=True)
    article_type: Mapped[str] = mapped_column(String(20), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Prompt(Base):
    """Agent Prompt 版本管理"""

    __tablename__ = "prompts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
