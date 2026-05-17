from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from config import get_settings
from db.database import get_db
from services.hot_pool import (
    ArticleSnippet,
    HotTickerModel,
    get_hot_pool_data_revision,
    get_hot_tickers_cached,
)

router = APIRouter()

# 与 services.hot_pool 一致，供 OpenAPI / 前端类型生成
HotTicker = HotTickerModel


@router.get("", response_model=List[HotTicker])
def hot_tickers(
    response: Response,
    db: Session = Depends(get_db),
    *,
    window_days: int | None = Query(None, ge=1, le=30, description="覆盖默认窗口天数"),
    pool_max: int | None = Query(None, ge=1, le=50, description="覆盖默认池上限"),
):
    """
    与「简讯 Pipeline」日级对齐：盘前/盘后简报落库或 purge 后修订号才变，不在其它场景频繁失效。
    响应头 `X-FOMO-Hot-Pool-Data-Revision` 为当前代数。简报快照仍用 compute_hot_tickers，不经此缓存。
    """
    settings = get_settings()
    days = window_days if window_days is not None else settings.hot_pool_window_days
    limit = pool_max if pool_max is not None else settings.hot_pool_max_size
    rows = get_hot_tickers_cached(db, window_days=days, pool_max=limit)
    response.headers["X-FOMO-Hot-Pool-Data-Revision"] = str(get_hot_pool_data_revision())
    return rows


__all__ = ["router", "ArticleSnippet", "HotTicker"]
