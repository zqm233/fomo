from __future__ import annotations

import uuid
from datetime import datetime, timezone

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


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Source(Base):
    """Twitter 博主 / 微信公众号 数据源配置"""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "twitter" | "wechat"
    handle: Mapped[str] = mapped_column(String(200), nullable=False)      # @username / 公众号ID
    description: Mapped[str] = mapped_column(Text, default="")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="ok")         # "ok" | "error"
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
    run_type: Mapped[str] = mapped_column(String(20), nullable=False)      # "pre" | "post" | "manual"
    status: Mapped[str] = mapped_column(String(20), default="queued")      # "queued"|"running"|"success"|"failed"
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_msg: Mapped[str] = mapped_column(Text, default="")
    articles_crawled: Mapped[int] = mapped_column(Integer, default=0)
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
