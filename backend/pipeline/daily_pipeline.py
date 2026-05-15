from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from db.database import SessionLocal
from db.models import PipelineRun, RawArticle, Source
from vector_store.chroma_store import add_documents
from crawlers.twitter_crawler import crawl_twitter
from crawlers.wechat_crawler import crawl_wechat
from agents.sentiment_agent import run_sentiment_agent
from agents.hotspot_agent import run_hotspot_agent
from agents.summary_agent import run_summary_agent
from services.stock_price import fetch_stock_prices, extract_tickers_from_text
from services.notifier import notify_report_ready
from tools.db_tool import save_report_direct

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _create_run(db, job_id: str, run_type: str) -> PipelineRun:
    run = PipelineRun(
        job_id=job_id,
        run_type=run_type,
        status="running",
        started_at=_now(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _finish_run(db, run: PipelineRun, success: bool, error: str = "") -> None:
    run.status = "success" if success else "failed"
    run.finished_at = _now()
    run.error_msg = error
    db.commit()


def run_pipeline(report_type: str = "pre", job_id: str | None = None) -> str:
    """
    Full automated pipeline: crawl → clean → store → vectorize → analyse → report.
    Returns the job_id for status polling.
    """
    if job_id is None:
        job_id = str(uuid.uuid4())

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    db = SessionLocal()
    run = _create_run(db, job_id, run_type=report_type)

    try:
        sources = db.query(Source).filter(Source.is_enabled == True).all()
        if not sources:
            logger.warning("No enabled sources found; skipping pipeline")
            _finish_run(db, run, success=True)
            return job_id

        all_texts: list[str] = []
        total_new = 0

        for source in sources:
            logger.info("Crawling source: %s (%s)", source.name, source.source_type)
            try:
                if source.source_type == "twitter":
                    crawl_result = crawl_twitter(source.handle)
                    items = crawl_result.tweets
                    crawl_error = crawl_result.error
                else:
                    crawl_result = crawl_wechat(source.handle)
                    items = crawl_result.articles
                    crawl_error = crawl_result.error

                if crawl_error:
                    source.status = "error"
                    db.commit()
                    logger.warning("Source %s marked as error: %s", source.name, crawl_error)
                    continue

                source.status = "ok"
                source.last_crawled_at = _now()
                db.commit()

                doc_ids, texts, metadatas = [], [], []
                for item in items:
                    content_hash = item["content_hash"]
                    existing = (
                        db.query(RawArticle)
                        .filter(RawArticle.content_hash == content_hash)
                        .first()
                    )
                    if existing:
                        continue

                    article = RawArticle(
                        source_id=source.id,
                        content=item["content"],
                        url=item["url"],
                        author=item["author"],
                        published_at=item["published_at"],
                        content_hash=content_hash,
                        vectorized=False,
                    )
                    db.add(article)
                    db.flush()

                    pub_date = ""
                    if item["published_at"]:
                        pub_date = item["published_at"].strftime("%Y-%m-%d")

                    doc_ids.append(article.id)
                    texts.append(item["content"])
                    metadatas.append(
                        {
                            "source_id": source.id,
                            "author": item["author"],
                            "url": item["url"],
                            "published_date": pub_date,
                            "article_type": source.source_type,
                        }
                    )
                    all_texts.append(item["content"])

                db.commit()

                if doc_ids:
                    added = add_documents(
                        source_id=source.id,
                        doc_ids=doc_ids,
                        texts=texts,
                        metadatas=metadatas,
                    )
                    db.query(RawArticle).filter(
                        RawArticle.id.in_(doc_ids)
                    ).update({"vectorized": True}, synchronize_session=False)
                    db.commit()
                    total_new += added
                    logger.info("Added %d new docs for source %s", added, source.name)

            except Exception as e:
                logger.error("Error processing source %s: %s", source.name, e)
                source.status = "error"
                db.commit()

        run.articles_crawled = total_new
        db.commit()

        source_ids = [s.id for s in sources]

        logger.info("Running sentiment analysis for %s", today)
        sentiment = run_sentiment_agent(source_ids=source_ids, date=today)

        logger.info("Running hotspot analysis for %s", today)
        hotspots = run_hotspot_agent(source_ids=source_ids, date=today)

        mentioned_tickers = extract_tickers_from_text(all_texts)
        hot_tickers = [t["ticker"] for t in hotspots.get("hot_tickers", [])]
        all_tickers = list(set(mentioned_tickers + hot_tickers))

        logger.info("Fetching stock prices for %d tickers", len(all_tickers))
        stock_prices = fetch_stock_prices(all_tickers)

        logger.info("Generating %s summary for %s", report_type, today)
        summary_text = run_summary_agent(
            source_ids=source_ids,
            date=today,
            report_type=report_type,
            sentiment=sentiment,
            hotspots=hotspots,
            stock_prices=stock_prices,
        )

        save_report_direct(
            {
                "report_date": today,
                "report_type": report_type,
                "sentiment": sentiment,
                "hotspots": hotspots,
                "stock_prices": stock_prices,
                "summary_text": summary_text,
                "article_count": total_new,
            }
        )

        notify_report_ready(
            report_date=today,
            report_type=report_type,
            sentiment_label=sentiment.get("label", "中性"),
            hotspot_count=len(hotspots.get("themes", [])),
            summary_preview=summary_text,
        )

        _finish_run(db, run, success=True)
        logger.info("Pipeline completed successfully: %s %s (job_id=%s)", today, report_type, job_id)

    except Exception as e:
        logger.exception("Pipeline failed: %s", e)
        _finish_run(db, run, success=False, error=str(e))
    finally:
        db.close()

    return job_id
