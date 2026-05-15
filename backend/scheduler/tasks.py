from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_scheduler: BackgroundScheduler | None = None
_ET = pytz.timezone("America/New_York")


def _run_pre_market():
    from pipeline.daily_pipeline import run_pipeline
    logger.info("Scheduled pre-market pipeline triggered")
    run_pipeline(report_type="pre")


def _run_post_market():
    from pipeline.daily_pipeline import run_pipeline
    logger.info("Scheduled post-market pipeline triggered")
    run_pipeline(report_type="post")


def start_scheduler() -> None:
    global _scheduler
    _scheduler = BackgroundScheduler(timezone=_ET)

    _scheduler.add_job(
        _run_pre_market,
        trigger=CronTrigger(
            hour=settings.pre_market_hour,
            minute=settings.pre_market_minute,
            timezone=_ET,
        ),
        id="pre_market",
        name="盘前简讯流水线",
        replace_existing=True,
    )

    _scheduler.add_job(
        _run_post_market,
        trigger=CronTrigger(
            hour=settings.post_market_hour,
            minute=settings.post_market_minute,
            timezone=_ET,
        ),
        id="post_market",
        name="盘后复盘流水线",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        "Scheduler started — pre-market %02d:%02d ET, post-market %02d:%02d ET",
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
