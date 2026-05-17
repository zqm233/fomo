from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import RawArticle, Source

router = APIRouter()


class ArticleOut(BaseModel):
    id: str
    source_id: str
    source_name: str
    content_type: str   # "daily" | "research"
    author: str
    title: str          # first line of content
    preview: str        # first ~150 chars of body
    content: str        # full text
    url: str
    published_at: Optional[str]
    created_at: str
    vectorized: bool


def _to_out(article: RawArticle, source: Source) -> ArticleOut:
    lines = article.content.strip().splitlines()
    title = lines[0].strip() if lines else ""
    body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
    preview = body[:150].rstrip() + ("…" if len(body) > 150 else "")

    def _iso(dt):
        if dt is None:
            return None
        s = dt.isoformat()
        if not s.endswith("Z") and "+" not in s[-6:]:
            s += "Z"
        return s

    return ArticleOut(
        id=article.id,
        source_id=article.source_id,
        source_name=source.name if source else "",
        content_type=source.content_type if source else "daily",
        author=article.author,
        title=title,
        preview=preview,
        content=article.content,
        url=article.url,
        published_at=_iso(article.published_at),
        created_at=_iso(article.created_at),
        vectorized=article.vectorized,
    )


@router.get("", response_model=List[ArticleOut])
def list_articles(
    source_id: Optional[str] = Query(None),
    content_type: Optional[str] = Query(None, description="daily | research"),
    q: Optional[str] = Query(None, description="全文关键词搜索"),
    limit: int = Query(40, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    sources = {s.id: s for s in db.query(Source).all()}

    query = (
        db.query(RawArticle)
        .join(Source, Source.id == RawArticle.source_id)
        .order_by(RawArticle.published_at.desc())
    )
    if source_id:
        query = query.filter(RawArticle.source_id == source_id)
    if content_type:
        query = query.filter(Source.content_type == content_type)
    if q:
        query = query.filter(RawArticle.content.contains(q))

    articles = query.offset(offset).limit(limit).all()
    return [_to_out(a, sources.get(a.source_id)) for a in articles]


@router.get("/count")
def count_articles(
    source_id: Optional[str] = Query(None),
    content_type: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(RawArticle).join(Source, Source.id == RawArticle.source_id)
    if source_id:
        query = query.filter(RawArticle.source_id == source_id)
    if content_type:
        query = query.filter(Source.content_type == content_type)
    if q:
        query = query.filter(RawArticle.content.contains(q))
    return {"count": query.count()}


@router.get("/{article_id}", response_model=ArticleOut)
def get_article(article_id: str, db: Session = Depends(get_db)):
    from fastapi import HTTPException
    article = db.query(RawArticle).filter(RawArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    source = db.query(Source).filter(Source.id == article.source_id).first()
    return _to_out(article, source)
