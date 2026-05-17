"""
热门股池：从 daily 类型 raw_articles 正文按「最近 N 个 NYSE 交易日」窗口统计（$TICKER + 别名），
与行情日线窗口对齐；不依赖 ticker_mentions 表。
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from config import get_settings
from db.models import RawArticle, Source
from services.market import extract_tickers_from_text
from services.nyse_calendar import datetime_to_nyse_session_date_str, nyse_session_dates_last_n

logger = logging.getLogger(__name__)

_cache_lock = threading.Lock()
# 简讯数据每变一次（入库、purge）则 +1；API 缓存与当前修订号一致则命中
_hot_pool_data_revision: int = 0
# (revision_when_built, param_key (days,limit), rows)
_hot_pool_cache_entry: tuple[int, tuple[int, int], list[HotTickerModel]] | None = None


def get_hot_pool_data_revision() -> int:
    """当前热门股输入数据代数；仅当 invalidate 后才会变。"""
    return _hot_pool_data_revision


def invalidate_hot_pool_cache() -> None:
    """
    递增修订号使 /api/tickers/hot 下次重算。
    主路径：定时或手动的盘前/盘后简讯 Pipeline 成功写入 Report 后（日级）。
    另：purge 删掉过期 daily 后数据源变了也会调用。
    """
    global _hot_pool_data_revision, _hot_pool_cache_entry
    with _cache_lock:
        _hot_pool_data_revision += 1
        _hot_pool_cache_entry = None
    logger.debug("hot_pool data revision -> %s", _hot_pool_data_revision)


def get_hot_tickers_cached(
    db: Session,
    *,
    window_days: int | None = None,
    pool_max: int | None = None,
) -> list[HotTickerModel]:
    """
    供 /api/tickers/hot：与当前 `_hot_pool_data_revision` 对齐则复用缓存。
    修订号在「盘前/盘后简讯 Pipeline 简报落库」或 purge 后递增（日级、非每次拉源）。
    简报内请仍用 compute_hot_tickers。
    """
    global _hot_pool_cache_entry
    settings = get_settings()
    days = window_days if window_days is not None else settings.hot_pool_window_days
    limit = pool_max if pool_max is not None else settings.hot_pool_max_size
    key = (days, limit)

    with _cache_lock:
        rev = _hot_pool_data_revision
        if _hot_pool_cache_entry is not None:
            cached_rev, k, rows = _hot_pool_cache_entry
            if cached_rev == rev and k == key:
                return rows

    rows = compute_hot_tickers(db, window_days=days, pool_max=limit)
    with _cache_lock:
        # 计算期间若发生过 invalidate，以最新 rev 为准再比一次
        rev = _hot_pool_data_revision
        _hot_pool_cache_entry = (rev, key, rows)
    return rows


class ArticleSnippet(BaseModel):
    article_id: str
    source_name: str
    preview: str
    url: str
    mention_date: str


class HotTickerModel(BaseModel):
    ticker: str
    mention_count: int
    sources: list[str]
    articles: list[ArticleSnippet]
    price: float | None = None
    change_pct: float | None = None
    sparkline: list[float] = []
    name: str = ""

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump()


@dataclass(frozen=True)
class _MentionEvent:
    ticker: str
    article_id: str
    source_id: str
    source_name: str
    mention_date: str  # NYSE 会话日 YYYY-MM-DD（与涨跌幅 K 线同为交易日语义）


def _gather_mention_events(
    db: Session, allowed_session_dates: frozenset[str], sql_lookback_days: int
) -> list[_MentionEvent]:
    """扫描 daily 简讯；仅统计归属日落在 allowed_session_dates（NYSE 交易日集合）内的提及。"""
    start = datetime.now(timezone.utc) - timedelta(days=sql_lookback_days)

    rows = (
        db.query(RawArticle, Source.id, Source.name)
        .join(Source, Source.id == RawArticle.source_id)
        .filter(Source.content_type == "daily")
        .filter(
            or_(
                RawArticle.published_at >= start,
                RawArticle.created_at >= start,
            )
        )
        .all()
    )

    events: list[_MentionEvent] = []
    for article, source_id, source_name in rows:
        t = article.published_at or article.created_at
        session_day = datetime_to_nyse_session_date_str(t)
        if session_day not in allowed_session_dates:
            continue
        tickers = extract_tickers_from_text([article.content])
        seen: set[str] = set()
        for tkr in tickers:
            u = tkr.strip().upper()
            if not u or u in seen:
                continue
            seen.add(u)
            events.append(
                _MentionEvent(
                    ticker=u,
                    article_id=article.id,
                    source_id=source_id,
                    source_name=source_name or "",
                    mention_date=session_day,
                )
            )
    return events


def _aggregate(
    events: list[_MentionEvent],
) -> tuple[dict[str, int], dict[str, set[str]], dict[str, set[str]], dict[str, list[_MentionEvent]]]:
    """博主×NYSE 交易日×标的 计 1 分；返回 scores, source_names, article_ids, events_by_ticker."""
    day_blogger: dict[str, set[tuple[str, str]]] = defaultdict(set)
    sources: dict[str, set[str]] = defaultdict(set)
    article_ids: dict[str, set[str]] = defaultdict(set)
    by_ticker: dict[str, list[_MentionEvent]] = defaultdict(list)

    for e in events:
        day_blogger[e.ticker].add((e.mention_date, e.source_id))
        sources[e.ticker].add(e.source_name)
        article_ids[e.ticker].add(e.article_id)
        by_ticker[e.ticker].append(e)

    scores = {t: len(pairs) for t, pairs in day_blogger.items()}
    return scores, sources, article_ids, by_ticker


def compute_hot_tickers(
    db: Session,
    *,
    window_days: int | None = None,
    pool_max: int | None = None,
) -> list[HotTickerModel]:
    """
    最近 N 个 NYSE 交易日内统计简讯提及；计分「博主×交易日×标的」。
    行情涨跌幅与同 N 的 period=Nd 日线一致（AkShare，按交易日）。
    """
    settings = get_settings()
    n_sessions = window_days if window_days is not None else settings.hot_pool_window_days
    limit = pool_max if pool_max is not None else settings.hot_pool_max_size

    allowed = nyse_session_dates_last_n(n_sessions)
    sql_lookback_days = max(45, n_sessions * 5 + 21)

    events = _gather_mention_events(db, allowed, sql_lookback_days)
    scores, ticker_sources, ticker_articles_map, mentions_by_ticker = _aggregate(events)
    if not scores:
        return []

    sorted_tickers = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]

    all_article_ids: set[str] = set()
    for sym, _ in sorted_tickers:
        all_article_ids |= ticker_articles_map[sym]

    articles_by_id: dict[str, RawArticle] = {}
    if all_article_ids:
        articles_by_id = {
            a.id: a
            for a in db.query(RawArticle).filter(RawArticle.id.in_(all_article_ids)).all()
        }

    price_data: dict[str, dict] = {}
    try:
        from services.market import fetch_ticker_history

        top_symbols = [sym for sym, _ in sorted_tickers]
        price_data = fetch_ticker_history(top_symbols, period=f"{n_sessions}d")
    except Exception:
        pass

    results: list[HotTickerModel] = []
    for ticker_sym, score in sorted_tickers:
        evs = sorted(
            mentions_by_ticker[ticker_sym],
            key=lambda e: e.mention_date,
            reverse=True,
        )
        seen_articles: set[str] = set()
        snippets: list[ArticleSnippet] = []
        for e in evs:
            if e.article_id in seen_articles:
                continue
            seen_articles.add(e.article_id)
            art = articles_by_id.get(e.article_id)
            if not art:
                continue
            lines = art.content.strip().splitlines()
            preview_text = " ".join(lines[:3])[:120]
            snippets.append(
                ArticleSnippet(
                    article_id=e.article_id,
                    source_name=e.source_name,
                    preview=preview_text,
                    url=art.url or "",
                    mention_date=e.mention_date,
                )
            )
            if len(snippets) >= 3:
                break

        pd = price_data.get(ticker_sym, {})
        results.append(
            HotTickerModel(
                ticker=ticker_sym,
                mention_count=score,
                sources=sorted(ticker_sources[ticker_sym]),
                articles=snippets,
                price=pd.get("price"),
                change_pct=pd.get("change_pct"),
                sparkline=pd.get("sparkline", []),
                name=pd.get("name", ticker_sym),
            )
        )

    return results
