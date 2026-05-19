from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.events import EVENT_JOB_MISSED
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from config import get_settings
from services.nyse_calendar import next_nyse_session_datetime_et

logger = logging.getLogger(__name__)
settings = get_settings()

_scheduler: BackgroundScheduler | None = None
# Align with nyse_calendar (ZoneInfo); avoids mixing pytz vs ZoneInfo on job fire comparisons.
_ET = ZoneInfo("America/New_York")


# ── pipeline callbacks ─────────────────────────────────────────────────────────

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


# ── scheduling helpers ─────────────────────────────────────────────────────────

def _schedule_pre_market() -> None:
    """Create pre_market job only if it doesn't already exist in the jobstore."""
    if not _scheduler:
        return
    if _scheduler.get_job("pre_market") is not None:
        job = _scheduler.get_job("pre_market")
        logger.info("pre_market job already in jobstore, next run: %s", job.next_run_time)
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
        misfire_grace_time=3600,
        coalesce=True,
    )
    logger.info("Next pre-market pipeline scheduled at %s", run_at.isoformat())


def _schedule_post_market() -> None:
    """Create post_market job only if it doesn't already exist in the jobstore."""
    if not _scheduler:
        return
    if _scheduler.get_job("post_market") is not None:
        job = _scheduler.get_job("post_market")
        logger.info("post_market job already in jobstore, next run: %s", job.next_run_time)
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
        misfire_grace_time=3600,
        coalesce=True,
    )
    logger.info("Next post-market pipeline scheduled at %s", run_at.isoformat())


def _on_job_missed(event) -> None:
    """
    When a job is missed beyond misfire_grace_time, APScheduler fires this event and
    removes the job from the store without calling the function. We reschedule it here
    so the next trading-day slot is always set up.
    """
    if event.job_id == "pre_market":
        logger.warning("pre_market missed beyond grace; scheduling next trading slot")
        _schedule_pre_market()
    elif event.job_id == "post_market":
        logger.warning("post_market missed beyond grace; scheduling next trading slot")
        _schedule_post_market()


# ── public API ─────────────────────────────────────────────────────────────────

def start_scheduler() -> None:
    global _scheduler
    jobstore = SQLAlchemyJobStore(url=settings.database_url)
    _scheduler = BackgroundScheduler(
        jobstores={"default": jobstore},
        timezone=_ET,
    )
    _scheduler.add_listener(_on_job_missed, EVENT_JOB_MISSED)

    _scheduler.start()

    # Create jobs only if they aren't already persisted in PostgreSQL.
    # Must be called AFTER start() so get_job() can query the jobstore.
    _schedule_pre_market()
    _schedule_post_market()
    logger.info(
        "Scheduler started with SQLAlchemy jobstore — pre-market %02d:%02d ET, "
        "post-market %02d:%02d ET (NYSE trading days only)",
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
