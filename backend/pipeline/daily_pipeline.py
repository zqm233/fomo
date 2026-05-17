from __future__ import annotations

import concurrent.futures
import json
import logging
import random
import time
import uuid
from datetime import datetime, timezone

# Step keys for each source crawl task
_STEP_FETCH     = ("fetch",    "获取 RSS")
_STEP_PARSE     = ("parse",    "解析去重")
_STEP_VECTORIZE = ("vectorize","向量化")

from db.database import SessionLocal
from db.models import PipelineRun, RawArticle, Source, SourceCrawlLog
from vector_store.chroma_store import add_documents
from crawlers.rss_crawler import crawl_rss
from agents.sentiment_agent import run_sentiment_agent
from agents.hotspot_agent import run_hotspot_agent
from agents.summary_agent import run_summary_agent
from services.hot_pool import compute_hot_tickers, invalidate_hot_pool_cache
from services.article_retention import purge_old_daily_articles
from services.market import fetch_market_snapshot, fetch_stock_prices, extract_tickers_from_text
from services.notifier import notify_report_ready
from tools.db_tool import save_report_direct

logger = logging.getLogger(__name__)

_DIGEST_PREVIEW_LEN = 280

# 盘后复盘行情卡：四大指数 + 最多 4 档「简讯≥2 次提及」的个股
_MAX_POST_EQUITY_SLOTS = 4


def _post_market_stock_prices_for_report(daily_articles: list[dict]) -> dict[str, dict]:
    """
    盘后复盘：先 SPY/QQQ/DIA/IWM，再按时间窗内简讯出现次数（≥2 条简讯提到过）排序个股，最多 4 只。
    出现次数按「简讯条」计：同一条里多次提到同代码只算该条计 1 次。
    """
    from collections import Counter

    from services.market.constants import INDICES, SECTORS

    index_order = list(INDICES.keys())
    excluded = set(index_order) | set(SECTORS.keys())

    counts: Counter[str] = Counter()
    for a in daily_articles:
        text = a.get("content") or ""
        tickers = extract_tickers_from_text([text])
        for t in {x.strip().upper() for x in tickers if x and str(x).strip()}:
            counts[t] += 1

    popular = [
        sym
        for sym, c in sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        if c >= 2 and sym not in excluded
    ][: _MAX_POST_EQUITY_SLOTS]

    fetch_symbols = index_order + popular
    raw = fetch_stock_prices(fetch_symbols)
    out: dict[str, dict] = {}
    for sym in index_order:
        if sym in raw:
            out[sym] = raw[sym]
    for sym in popular:
        if sym in raw:
            out[sym] = raw[sym]
    return out


def _source_digest_rows(daily_by_source: dict[str, list[str]]) -> list[dict]:
    """Per-blogger rows for UI: name, 简讯条数 in window, first item preview."""
    rows: list[dict[str, str | int]] = []
    for name, texts in daily_by_source.items():
        name = (name or "").strip()
        if not name:
            continue
        first = (texts[0] if texts else "") or ""
        first = first.strip()
        prev = first[:_DIGEST_PREVIEW_LEN] + ("…" if len(first) > _DIGEST_PREVIEW_LEN else "")
        rows.append(
            {
                "source_name": name,
                "item_count": len(texts),
                "preview": prev.replace("\n", " "),
            }
        )
    rows.sort(key=lambda r: (-int(r["item_count"]), str(r["source_name"])))
    return rows


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fetch_daily_articles_window(db, hours: int) -> list[dict]:
    """
    Fetch daily-source article contents published within the last `hours` hours.
    Returns list of {source_name, content} dicts.
    These go directly to agents (not in ChromaDB).
    """
    from datetime import timedelta
    cutoff = _now() - timedelta(hours=hours)
    rows = (
        db.query(RawArticle.content, Source.name)
        .join(Source, Source.id == RawArticle.source_id)
        .filter(
            Source.content_type == "daily",
            RawArticle.published_at >= cutoff,
        )
        .order_by(RawArticle.published_at.desc())
        .limit(100)
        .all()
    )
    return [
        {"source_name": source_name or "", "content": content}
        for content, source_name in rows
        if content
    ]


def _create_run(db, job_id: str, run_type: str) -> PipelineRun:
    run = db.query(PipelineRun).filter(PipelineRun.job_id == job_id).first()
    if run is None:
        run = PipelineRun(job_id=job_id, run_type=run_type)
        db.add(run)
    run.status = "running"
    run.started_at = _now()
    db.commit()
    db.refresh(run)
    return run


def _finish_run(db, run: PipelineRun, success: bool, error: str = "") -> None:
    run.status = "success" if success else "failed"
    run.finished_at = _now()
    run.error_msg = error
    db.commit()


_CRAWL_TIMEOUT = 90  # seconds per source before giving up


def _set_step(db, task_log: SourceCrawlLog, step: tuple, status: str, detail: str = "") -> None:
    """Update a named step's status in task_log.steps (JSON) and commit."""
    key, name = step
    steps = json.loads(task_log.steps or "[]")
    for s in steps:
        if s["key"] == key:
            s["status"] = status
            s["detail"] = detail
            break
    else:
        steps.append({"key": key, "name": name, "status": status, "detail": detail})
    task_log.steps = json.dumps(steps, ensure_ascii=False)
    db.commit()


def _crawl_one_source(db, source: Source, job_id: str, task_log: SourceCrawlLog) -> int:
    """Crawl a single source, update task_log in-place. Returns count of new docs added."""
    def _progress(msg: str):
        task_log.error_msg = msg
        db.commit()

    task_log.status = "running"
    task_log.started_at = _now()
    task_log.steps = "[]"

    # ── Step 1: Fetch RSS ──────────────────────────────────────────────────────
    _set_step(db, task_log, _STEP_FETCH, "running")

    try:
        # Run the actual network crawl in a thread with a hard timeout
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(crawl_rss, source.handle)
            try:
                crawl_result = future.result(timeout=_CRAWL_TIMEOUT)
            except concurrent.futures.TimeoutError:
                raise TimeoutError(
                    f"获取超时（>{_CRAWL_TIMEOUT}s），请检查网络或稍后重试"
                )

        items, crawl_error = crawl_result.articles, crawl_result.error

        if crawl_error:
            _set_step(db, task_log, _STEP_FETCH, "failed", crawl_error)
            _set_step(db, task_log, _STEP_PARSE, "failed", "上游失败")
            _set_step(db, task_log, _STEP_VECTORIZE, "failed", "上游失败")
            source.status = "error"
            task_log.status = "failed"
            task_log.error_msg = crawl_error
            task_log.finished_at = _now()
            db.commit()
            logger.warning("Source %s error: %s", source.name, crawl_error)
            return 0

        _set_step(db, task_log, _STEP_FETCH, "success", f"获取 {len(items)} 篇")
        source.status = "ok"
        source.last_crawled_at = _now()
        db.commit()

        # ── Step 2: Parse & deduplicate ────────────────────────────────────────
        _set_step(db, task_log, _STEP_PARSE, "running")
        doc_ids, texts, metadatas = [], [], []
        for item in items:
            if db.query(RawArticle.id).filter(RawArticle.url == item["url"]).first():
                continue
            article = RawArticle(
                source_id=source.id,
                content=item["content"],
                url=item["url"],
                author=item["author"],
                published_at=item["published_at"],
                content_hash=item["content_hash"],
                vectorized=False,
            )
            db.add(article)
            db.flush()
            if item.get("published_at"):
                pub_date = item["published_at"].strftime("%Y-%m-%d")
            else:
                pub_date = article.created_at.strftime("%Y-%m-%d")
            doc_ids.append(article.id)
            texts.append(item["content"])
            metadatas.append({
                "source_id": source.id,
                "author": item["author"],
                "url": item["url"],
                "published_date": pub_date,
                "article_type": source.source_type,
            })
        db.commit()

        skipped = len(items) - len(doc_ids)
        parse_detail = f"新增 {len(doc_ids)} 篇" + (f"，跳过重复 {skipped} 篇" if skipped else "")
        _set_step(db, task_log, _STEP_PARSE, "success", parse_detail)

        # ── Step 3: Vectorize (research sources only) ─────────────────────────
        added = 0
        if source.content_type == "research":
            if doc_ids:
                _set_step(db, task_log, _STEP_VECTORIZE, "running")
                added = add_documents(source_id=source.id, doc_ids=doc_ids, texts=texts, metadatas=metadatas)
                db.query(RawArticle).filter(RawArticle.id.in_(doc_ids)).update(
                    {"vectorized": True}, synchronize_session=False
                )
                db.commit()
                _set_step(db, task_log, _STEP_VECTORIZE, "success", f"{added} 篇入库")
            else:
                _set_step(db, task_log, _STEP_VECTORIZE, "success", "无新内容")
        else:
            # daily sources go straight to DB, no RAG needed
            _set_step(db, task_log, _STEP_VECTORIZE, "success", "跳过（日常简讯）")

        task_log.status = "success"
        task_log.articles_found = len(doc_ids)
        task_log.error_msg = ""
        task_log.finished_at = _now()
        db.commit()
        return added

    except Exception as e:
        logger.error("Error processing source %s: %s", source.name, e)
        # Mark any still-running step as failed
        steps = json.loads(task_log.steps or "[]")
        for s in steps:
            if s["status"] == "running":
                s["status"] = "failed"
                s["detail"] = str(e)[:80]
        task_log.steps = json.dumps(steps, ensure_ascii=False)
        source.status = "error"
        task_log.status = "failed"
        task_log.error_msg = str(e)
        task_log.finished_at = _now()
        db.commit()
        return 0


def crawl_single_source(source_id: str, job_id: str | None = None, run_type: str = "single_sync") -> str:
    """Crawl a single source in its own mini pipeline run. Returns job_id."""
    if job_id is None:
        job_id = str(uuid.uuid4())

    db = SessionLocal()
    try:
        source = db.query(Source).filter(Source.id == source_id).first()
        if not source:
            raise ValueError(f"Source {source_id} not found")

        run = PipelineRun(job_id=job_id, run_type=run_type, status="running", started_at=_now())
        db.add(run)
        db.commit()

        task_log = SourceCrawlLog(
            job_id=job_id,
            source_id=source.id,
            source_name=source.name,
            source_type=source.source_type,
            status="pending",
        )
        db.add(task_log)
        db.commit()

        _crawl_one_source(db, source, job_id, task_log)
        _finish_run(db, run, success=(task_log.status == "success"))
    except Exception as e:
        logger.exception("crawl_single_source failed: %s", e)
    finally:
        db.close()
    return job_id


def run_pipeline(
    report_type: str = "pre",
    job_id: str | None = None,
    *,
    skip_crawl: bool = False,
) -> str:
    """
    Full automated pipeline: crawl → clean → store → vectorize → analyse → report.
    盘前/盘后（pre/post）：若美东当日非 NYSE 交易日（周末或休市），不生成简报并标记任务成功+跳过原因。
    When skip_crawl=True (仅 pre/post): 不爬 RSS、不向量化，仅用库内时间窗内的 daily 简讯 +
    仍拉取行情与生成简报。用于快速调试行情与文案逻辑。
    Returns the job_id for status polling.
    """
    if job_id is None:
        job_id = str(uuid.uuid4())

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    db = SessionLocal()
    run = _create_run(db, job_id, run_type=report_type)

    if report_type in ("pre", "post"):
        from services.nyse_calendar import is_nyse_trading_day_et

        if not is_nyse_trading_day_et():
            skip_msg = "已跳过：美东当日非 NYSE 交易日（周末或休市），不生成简报"
            logger.info("%s (job_id=%s)", skip_msg, job_id)
            _finish_run(db, run, success=True, error=skip_msg)
            db.close()
            return job_id

    # 仅盘前/盘后简报支持「不拉新」：跳过 RSS 与向量化补偿，仍读库内 daily 简讯并拉行情
    skip_data_fetch = bool(skip_crawl) and report_type in ("pre", "post")

    try:
        sources = db.query(Source).filter(Source.is_enabled == True).all()
        if not sources and not skip_data_fetch:
            logger.warning("No enabled sources found; skipping pipeline")
            _finish_run(db, run, success=True)
            return job_id

        total_new = 0

        if skip_data_fetch:
            run.error_msg = "跳过数据源抓取，读取库内简讯…"
            db.commit()
            logger.info(
                "skip_crawl=True: skipping RSS crawl and vector backfill (job_id=%s)",
                job_id,
            )

        if not skip_data_fetch:
            if not sources:
                logger.warning("No enabled sources found; skipping pipeline")
                _finish_run(db, run, success=True)
                return job_id

            # 预先创建所有 source 的 pending 任务记录
            task_logs: dict[str, SourceCrawlLog] = {}
            for source in sources:
                log = SourceCrawlLog(
                    job_id=job_id,
                    source_id=source.id,
                    source_name=source.name,
                    source_type=source.source_type,
                    status="pending",
                )
                db.add(log)
                task_logs[source.id] = log
            db.commit()

            for i, source in enumerate(sources):
                # Check cancellation before each source
                db.refresh(run)
                if run.cancel_requested:
                    logger.info("Pipeline cancelled by user, stopping after current source")
                    for remaining_log in task_logs.values():
                        if remaining_log.status == "pending":
                            remaining_log.status = "failed"
                            remaining_log.error_msg = "已取消"
                            remaining_log.finished_at = _now()
                    db.commit()
                    _finish_run(db, run, success=False, error="用户取消")
                    return job_id

                # Random delay between sources to avoid triggering anti-crawl
                if i > 0:
                    delay = random.uniform(5, 20)
                    logger.info("Waiting %.1fs before next source (%s)…", delay, source.name)
                    time.sleep(delay)

                task_log = task_logs[source.id]
                logger.info("Crawling source: %s (%s)", source.name, source.source_type)
                added = _crawl_one_source(db, source, job_id, task_log)
                total_new += added

            run.articles_crawled = total_new

            # Backfill any research-source articles that were saved but never vectorized
            unvectorized = (
                db.query(RawArticle)
                .join(Source, Source.id == RawArticle.source_id)
                .filter(RawArticle.vectorized == False, Source.content_type == "research")  # noqa: E712
                .all()
            )
            if unvectorized:
                run.error_msg = "补偿向量化中…"
                db.commit()
                by_source: dict[str, list[RawArticle]] = {}
                for a in unvectorized:
                    by_source.setdefault(a.source_id, []).append(a)
                for sid, articles in by_source.items():
                    try:
                        added_back = add_documents(
                            source_id=sid,
                            doc_ids=[a.id for a in articles],
                            texts=[a.content for a in articles],
                            metadatas=[
                                {
                                    "source_id": a.source_id,
                                    "author": a.author or "",
                                    "url": a.url or "",
                                    "published_date": a.published_at.strftime("%Y-%m-%d") if a.published_at else "",
                                    "article_type": "rss",
                                }
                                for a in articles
                            ],
                        )
                        if added_back:
                            db.query(RawArticle).filter(
                                RawArticle.id.in_([a.id for a in articles])
                            ).update({"vectorized": True}, synchronize_session=False)
                            db.commit()
                            logger.info("Backfilled %d vectors for source %s", added_back, sid)
                    except Exception as e:
                        logger.warning("Backfill vectorization failed for source %s: %s", sid, e)

        # Manual triggers only crawl + vectorize; scheduled runs also analyse + report
        if report_type in ("pre", "post"):
            # ── Fetch daily articles in time window ────────────────────────────
            # pre-market: cover overnight news (last 20h)
            # post-market: cover market session (last 14h, from roughly US open)
            window_hours = 14 if report_type == "post" else 20
            daily_articles = _fetch_daily_articles_window(db, hours=window_hours)
            daily_texts = [a["content"] for a in daily_articles]

            # Group by source for per-blogger breakdown in summary
            daily_by_source: dict[str, list[str]] = {}
            for a in daily_articles:
                daily_by_source.setdefault(a["source_name"], []).append(a["content"])

            logger.info(
                "Fetched %d daily articles (%d sources) in %dh window for %s report",
                len(daily_texts), len(daily_by_source), window_hours, report_type,
            )

            run.error_msg = "AI 分析中：情绪分析…"
            db.commit()
            logger.info("Running sentiment analysis for %s", today)
            sentiment = run_sentiment_agent(
                date=today,
                daily_by_source=daily_by_source,
            )

            run.error_msg = "AI 分析中：热点提取…"
            db.commit()
            logger.info("Running hotspot analysis for %s", today)
            hotspots = run_hotspot_agent(
                date=today,
                daily_by_source=daily_by_source,
            )

            all_texts = daily_texts[:]
            mentioned_tickers = extract_tickers_from_text(all_texts)
            hot_tickers = [t["ticker"] for t in hotspots.get("hot_tickers", [])]
            all_tickers = list(set(mentioned_tickers + hot_tickers))

            if report_type == "post":
                run.error_msg = "获取盘后复盘行情（指数优先 + 简讯热门股）…"
                db.commit()
                stock_prices = _post_market_stock_prices_for_report(daily_articles)
                logger.info(
                    "Post-market stock row: %d symbols (indices + ≥2-mention equities)",
                    len(stock_prices),
                )
            else:
                run.error_msg = f"获取股价数据（{len(all_tickers)} 个标的）…"
                db.commit()
                logger.info("Fetching stock prices for %d tickers", len(all_tickers))
                stock_prices = fetch_stock_prices(all_tickers)

            # ── Fetch market snapshot for post-market (index + sector perf) ────
            market_snapshot: dict = {}
            if report_type == "post":
                run.error_msg = "获取市场行情数据…"
                db.commit()
                logger.info("Fetching market snapshot for post-market report")
                market_snapshot = fetch_market_snapshot()

            run.error_msg = "AI 分析中：生成简报…"
            db.commit()
            logger.info("Generating %s summary for %s", report_type, today)
            summary_text = run_summary_agent(
                date=today,
                report_type=report_type,
                sentiment=sentiment,
                hotspots=hotspots,
                stock_prices=stock_prices,
                daily_texts=daily_texts,
                daily_by_source=daily_by_source,
                market_snapshot=market_snapshot,
            )

            run.error_msg = "统计热门股池（简报快照）…"
            db.commit()
            hot_pool_snapshot = [m.to_json_dict() for m in compute_hot_tickers(db)]
            logger.info(
                "Hot pool snapshot for %s %s briefing: %d tickers",
                today,
                report_type,
                len(hot_pool_snapshot),
            )

            save_report_direct(
                {
                    "report_date": today,
                    "report_type": report_type,
                    "sentiment": sentiment,
                    "hotspots": hotspots,
                    "stock_prices": stock_prices,
                    "summary_text": summary_text,
                    # 本次简报分析所依据的时间窗内简讯条数（非「简报篇数」）
                    "article_count": len(daily_texts),
                    "source_digest": _source_digest_rows(daily_by_source),
                    "hot_pool": hot_pool_snapshot,
                }
            )

            # 热门股 API：仅在本轮「盘前/盘后简讯 Pipeline」简报落库后 bump（日级节奏；不在单次拉源/裸爬阶段失效）
            invalidate_hot_pool_cache()

            notify_report_ready(
                report_date=today,
                report_type=report_type,
                sentiment_label=sentiment.get("label", "中性"),
                hotspot_count=len(hotspots.get("themes", [])),
                summary_preview=summary_text,
            )

            if report_type == "post":
                run.error_msg = "清理过期简讯…"
                db.commit()
                purge_old_daily_articles()

        _finish_run(db, run, success=True)
        logger.info("Pipeline completed successfully: %s %s (job_id=%s)", today, report_type, job_id)

    except Exception as e:
        logger.exception("Pipeline failed: %s", e)
        _finish_run(db, run, success=False, error=str(e))
    finally:
        db.close()

    return job_id
