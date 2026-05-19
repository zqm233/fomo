"""日常简讯保留策略：删除超过 N 天的 daily 源文章（与 hot_pool_window_days 一致）。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from config import get_settings
from db.database import SessionLocal
from db.models import RawArticle, Source
from services.hot_pool import invalidate_hot_pool_cache

logger = logging.getLogger(__name__)


def purge_old_daily_articles() -> int:
    """
    删除日常简讯中早于保留窗口的文章（单独事务）；返回删除条数。
    """
    settings = get_settings()
    days = settings.hot_pool_window_days
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    db = SessionLocal()
    try:
        # ORM Query.delete() 不允许在已 join 的 Query 上调用；用 Core delete + 子查询
        id_subq = (
            select(RawArticle.id)
            .join(Source, Source.id == RawArticle.source_id)
            .where(Source.content_type == "daily")
            .where(
                func.coalesce(RawArticle.published_at, RawArticle.created_at) < cutoff
            )
        )
        result = db.execute(delete(RawArticle).where(RawArticle.id.in_(id_subq)))
        deleted = result.rowcount or 0
        db.commit()
        if deleted:
            logger.info(
                "Purged %d daily articles older than %d days",
                deleted,
                days,
            )
            invalidate_hot_pool_cache()
        return deleted
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
