from __future__ import annotations

import re
import uuid
from typing import List, Literal, Optional
from urllib.parse import urlparse, unquote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import get_settings
from db.database import get_db
from db.models import Source
from vector_store.pg_store import delete_collection, get_collection_stats

router = APIRouter()


def _unquote_path_segment(seg: str) -> str:
    """Decode %-encoding from URL path fragments."""
    try:
        return unquote(seg)
    except Exception:
        return seg


def _normalize_twitter_screen_name(raw: str) -> str:
    """Strip @ ; accept plain handle or pasted RSSHub / twitter user URL fragments."""
    s = (raw or "").strip().strip("\ufeff")
    if not s:
        return ""
    if s.startswith("@"):
        s = s[1:]
    if "://" in s:
        parsed = urlparse(s)
        segs = [x for x in parsed.path.strip("/").split("/") if x]
        if "user" in segs:
            i = segs.index("user")
            if i + 1 < len(segs):
                return _unquote_path_segment(segs[i + 1])
        return _unquote_path_segment(segs[-1]) if segs else ""
    s = re.split(r"[\s?#]", s, maxsplit=1)[0]
    part = s.strip("/").split("/")[-1]
    return _unquote_path_segment(part)


def resolve_feed_handle(feed_kind: str, *, handle: str, twitter_username: str) -> str:
    fk = feed_kind.strip().lower()
    if fk == "rsshub_twitter":
        uname = _normalize_twitter_screen_name(twitter_username or handle)
        if not uname:
            raise HTTPException(
                status_code=400,
                detail="请选择「Twitter（RSSHub）」时填写用户名，或粘贴完整 RSSHub URL",
            )
        base = get_settings().rsshub_twitter_base.rstrip("/")
        return f"{base}/{uname}"
    if fk == "custom":
        url = handle.strip().strip("\ufeff")
        if not url:
            raise HTTPException(status_code=400, detail="RSS URL 不能为空")
        return url
    raise HTTPException(status_code=400, detail="feed_kind 必须为 custom 或 rsshub_twitter")


class SourceCreate(BaseModel):
    """RSS 源：custom = 手写 URL；rsshub_twitter = RSSHub /twitter/user/<用户名>"""

    name: str
    source_type: str  # always "rss" for now
    handle: str = ""  # RSS URL when feed_kind == custom（Twitter 模式下可放空，用 twitter_username）
    twitter_username: str = ""
    description: Optional[str] = ""
    content_type: Optional[str] = "daily"  # "daily" | "research"


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    handle: Optional[str] = None
    twitter_username: Optional[str] = None
    feed_kind: Optional[Literal["custom", "rsshub_twitter"]] = None
    description: Optional[str] = None
    content_type: Optional[str] = None
    is_enabled: Optional[bool] = None


class SourceOut(BaseModel):
    id: str
    name: str
    source_type: str
    handle: str
    description: str
    content_type: str
    is_enabled: bool
    status: str
    last_crawled_at: Optional[str]
    created_at: str
    doc_count: int = 0

    class Config:
        from_attributes = True


def _to_out(source: Source) -> SourceOut:
    stats = get_collection_stats(source.id)
    return SourceOut(
        id=source.id,
        name=source.name,
        source_type=source.source_type,
        handle=source.handle,
        description=source.description,
        content_type=source.content_type,
        is_enabled=source.is_enabled,
        status=source.status,
        last_crawled_at=source.last_crawled_at.isoformat() if source.last_crawled_at else None,
        created_at=source.created_at.isoformat(),
        doc_count=stats["document_count"],
    )


@router.get("", response_model=List[SourceOut])
def list_sources(db: Session = Depends(get_db)):
    sources = db.query(Source).order_by(Source.created_at.desc()).all()
    return [_to_out(s) for s in sources]


@router.post("", response_model=SourceOut, status_code=201)
def create_source(body: SourceCreate, db: Session = Depends(get_db)):
    if body.source_type not in ("rss",):
        raise HTTPException(status_code=400, detail="source_type must be 'rss'")
    if body.content_type not in ("daily", "research"):
        raise HTTPException(status_code=400, detail="content_type must be 'daily' or 'research'")
    rss_url = resolve_feed_handle(
        body.feed_kind,
        handle=body.handle,
        twitter_username=body.twitter_username,
    )
    source = Source(
        id=str(uuid.uuid4()),
        name=body.name,
        source_type=body.source_type,
        handle=rss_url,
        description=body.description or "",
        content_type=body.content_type or "daily",
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return _to_out(source)


@router.get("/{source_id}", response_model=SourceOut)
def get_source(source_id: str, db: Session = Depends(get_db)):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return _to_out(source)


@router.patch("/{source_id}", response_model=SourceOut)
def update_source(source_id: str, body: SourceUpdate, db: Session = Depends(get_db)):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if body.name is not None:
        source.name = body.name
    if body.feed_kind is not None:
        rss_url = resolve_feed_handle(
            body.feed_kind,
            handle=(body.handle or "").strip(),
            twitter_username=(body.twitter_username or "").strip(),
        )
        source.handle = rss_url
    elif body.handle is not None:
        source.handle = body.handle.strip().strip("\ufeff")
    if body.description is not None:
        source.description = body.description
    if body.content_type is not None:
        if body.content_type not in ("daily", "research"):
            raise HTTPException(status_code=400, detail="content_type must be 'daily' or 'research'")
        source.content_type = body.content_type
    if body.is_enabled is not None:
        source.is_enabled = body.is_enabled
    db.commit()
    db.refresh(source)
    return _to_out(source)


@router.delete("/{source_id}", status_code=204)
def delete_source(source_id: str, db: Session = Depends(get_db)):
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    delete_collection(source_id)
    db.delete(source)
    db.commit()
