from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Source
from vector_store.chroma_store import delete_collection, get_collection_stats

router = APIRouter()


class SourceCreate(BaseModel):
    name: str
    source_type: str  # "rss"
    handle: str       # RSS feed URL
    description: Optional[str] = ""
    content_type: Optional[str] = "daily"  # "daily" | "research"


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    handle: Optional[str] = None
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
    source = Source(
        id=str(uuid.uuid4()),
        name=body.name,
        source_type=body.source_type,
        handle=body.handle.strip().strip("\ufeff"),
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
    if body.handle is not None:
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
