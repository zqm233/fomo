from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import pytz

from config import get_settings
from services.nyse_calendar import next_nyse_session_datetime_et

logger = logging.getLogger(__name__)
settings = get_settings()

_scheduler: BackgroundScheduler | None = None
_ET = pytz.timezone("America/New_York")


def _run_pre_market():
    from pipeline.daily_pipeline import run_pipeline

    logger.info("Scheduled pre-market pipeline triggered")
    try:
        run_pipeline(report_type="pre")
    finally:
        _schedule_pre_market()


def _run_post_market():
    from pipeline.daily_pipeline import run_pipeline

    logger.info("Scheduled post-market pipeline triggered")
    try:
        run_pipeline(report_type="post")
    finally:
        _schedule_post_market()


def _schedule_pre_market() -> None:
    if not _scheduler:
        return
    run_at = next_nyse_session_datetime_et(
        settings.pre_market_hour,
        settings.pre_market_minute,
    )
    _scheduler.add_job(
        _run_pre_market,
        trigger=DateTrigger(run_date=run_at, timezone=_ET),
        id="pre_market",
        name="盘前简报",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
    )
    logger.info("Next pre-market pipeline scheduled at %s", run_at.isoformat())


def _schedule_post_market() -> None:
    if not _scheduler:
        return
    run_at = next_nyse_session_datetime_et(
        settings.post_market_hour,
        settings.post_market_minute,
    )
    _scheduler.add_job(
        _run_post_market,
        trigger=DateTrigger(run_date=run_at, timezone=_ET),
        id="post_market",
        name="盘后简报",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
    )
    logger.info("Next post-market pipeline scheduled at %s", run_at.isoformat())


def start_scheduler() -> None:
    global _scheduler
    _scheduler = BackgroundScheduler(timezone=_ET)

    _schedule_pre_market()
    _schedule_post_market()

    _scheduler.start()
    logger.info(
        "Scheduler started — pre-market %02d:%02d ET, post-market %02d:%02d ET "
        "(NYSE trading days only; daily retention purge runs after post-market pipeline)",
        settings.pre_market_hour,
        settings.pre_market_minute,
        settings.post_market_hour,
        settings.post_market_minute,
    )


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def get_scheduler_status() -> list[dict]:
    if not _scheduler:
        return []
    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run": next_run.isoformat() if next_run else None,
            }
        )
    return jobs
