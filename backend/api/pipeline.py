from __future__ import annotations

import hmac
import threading
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import PipelineRun, SourceCrawlLog
from scheduler.tasks import get_scheduler_status
from config import get_settings

router = APIRouter()


def _iso(dt) -> str | None:
    """Serialize datetime to ISO string, always with Z suffix so browsers parse as UTC."""
    if dt is None:
        return None
    s = dt.isoformat()
    # SQLite returns naive datetimes; mark them as UTC explicitly
    if not s.endswith("Z") and "+" not in s[-6:]:
        s += "Z"
    return s


class TriggerRequest(BaseModel):
    report_type: str = "pre"  # "pre" | "post" | "manual"
    # 仅当 report_type 为 pre/post 时有效：不爬 RSS、不向量化，用库内简讯，仍拉行情
    skip_crawl: bool = False


class JobStatusOut(BaseModel):
    job_id: str
    run_type: str
    status: str
    started_at: Optional[str]
    finished_at: Optional[str]
    error_msg: str
    articles_crawled: int
    created_at: str


class TriggerResponse(BaseModel):
    job_id: str
    message: str


def _to_out(run: PipelineRun) -> JobStatusOut:
    return JobStatusOut(
        job_id=run.job_id,
        run_type=run.run_type,
        status=run.status,
        started_at=_iso(run.started_at),
        finished_at=_iso(run.finished_at),
        error_msg=run.error_msg,
        articles_crawled=run.articles_crawled,
        created_at=_iso(run.created_at),
    )


def _run_async(job_id: str, report_type: str, skip_crawl: bool = False):
    from pipeline.daily_pipeline import run_pipeline
    run_pipeline(report_type=report_type, job_id=job_id, skip_crawl=skip_crawl)


def _retry_async(source_id: str, job_id: str):
    from pipeline.daily_pipeline import crawl_single_source
    crawl_single_source(source_id=source_id, job_id=job_id)


def _reembed_research_async(job_id: str):
    from pipeline.daily_pipeline import run_research_reembed_job

    run_research_reembed_job(job_id)


@router.post("/sources/{source_id}/crawl", response_model=TriggerResponse)
def crawl_source(source_id: str, db: Session = Depends(get_db)):
    """立即爬取单个数据源。"""
    from db.models import Source
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    job_id = str(uuid.uuid4())
    thread = threading.Thread(
        target=_retry_async,
        args=(source_id, job_id),
        daemon=True,
    )
    thread.start()
    return TriggerResponse(job_id=job_id, message=f"正在抓取 {source.name}")


@router.post("/trigger", response_model=TriggerResponse)
def trigger_pipeline(body: TriggerRequest, db: Session = Depends(get_db)):
    job_id = str(uuid.uuid4())

    run = PipelineRun(job_id=job_id, run_type=body.report_type, status="queued")
    db.add(run)
    db.commit()

    thread = threading.Thread(
        target=_run_async,
        args=(job_id, body.report_type, body.skip_crawl),
        daemon=True,
    )
    thread.start()

    return TriggerResponse(job_id=job_id, message="流水线已启动，请通过 job_id 轮询状态")


@router.post("/research/reembed-vectors", response_model=TriggerResponse)
def reembed_research_vectors(
    x_reembed_secret: str | None = Header(None, alias="X-Reembed-Secret"),
    db: Session = Depends(get_db),
):
    """
    Temporary maintenance: drop all pgvector rows for research sources, then
    re-chunk and re-embed every stored article. Requires RESEARCH_REEMBED_SECRET
    and matching X-Reembed-Secret header (constant-time compare).
    Poll GET /api/pipeline/jobs/{job_id} until status is success or failed.
    """
    settings = get_settings()
    expected = settings.research_reembed_secret
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="RESEARCH_REEMBED_SECRET is not set; endpoint disabled",
        )
    got = (x_reembed_secret or "").strip()
    if not got or not hmac.compare_digest(got, expected):
        raise HTTPException(status_code=403, detail="Invalid or missing X-Reembed-Secret")

    job_id = str(uuid.uuid4())
    run = PipelineRun(job_id=job_id, run_type="reembed", status="queued")
    db.add(run)
    db.commit()

    thread = threading.Thread(
        target=_reembed_research_async,
        args=(job_id,),
        daemon=True,
    )
    thread.start()

    return TriggerResponse(
        job_id=job_id,
        message="Research re-embed started; poll GET /api/pipeline/jobs/{job_id}",
    )


@router.get("/jobs/{job_id}", response_model=JobStatusOut)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    run = db.query(PipelineRun).filter(PipelineRun.job_id == job_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_out(run)


@router.get("/jobs", response_model=List[JobStatusOut])
def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    runs = (
        db.query(PipelineRun)
        .order_by(PipelineRun.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_to_out(r) for r in runs]


class SourceTaskOut(BaseModel):
    id: str
    source_id: str
    source_name: str
    source_type: str
    status: str
    articles_found: int
    error_msg: str
    steps: list
    started_at: Optional[str]
    finished_at: Optional[str]


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    run = db.query(PipelineRun).filter(PipelineRun.job_id == job_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Job not found")
    if run.status not in ("queued", "running"):
        raise HTTPException(status_code=400, detail="Job is not running")

    now = datetime.now(timezone.utc)

    # Immediately mark job as failed so UI updates right away.
    # The background thread will see cancel_requested and stop cleanly.
    run.cancel_requested = True
    run.status = "failed"
    run.finished_at = now
    run.error_msg = "用户取消"

    # Also immediately mark any pending/running tasks as failed
    db.query(SourceCrawlLog).filter(
        SourceCrawlLog.job_id == job_id,
        SourceCrawlLog.status.in_(["pending", "running"]),
    ).update(
        {"status": "failed", "error_msg": "用户取消", "finished_at": now},
        synchronize_session=False,
    )
    db.commit()
    return {"message": "已终止"}


@router.post("/tasks/{task_id}/retry", response_model=TriggerResponse)
def retry_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(SourceCrawlLog).filter(SourceCrawlLog.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    new_job_id = str(uuid.uuid4())
    thread = threading.Thread(
        target=_retry_async,
        args=(task.source_id, new_job_id),
        daemon=True,
    )
    thread.start()
    return TriggerResponse(job_id=new_job_id, message=f"正在重试 {task.source_name}")


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(SourceCrawlLog).filter(SourceCrawlLog.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status in ("pending", "running"):
        raise HTTPException(status_code=400, detail="不能删除进行中的任务")
    db.delete(task)
    db.commit()


@router.get("/jobs/{job_id}/tasks", response_model=List[SourceTaskOut])
def get_job_tasks(job_id: str, db: Session = Depends(get_db)):
    logs = (
        db.query(SourceCrawlLog)
        .filter(SourceCrawlLog.job_id == job_id)
        .order_by(SourceCrawlLog.created_at)
        .all()
    )
    import json as _json
    return [
        SourceTaskOut(
            id=t.id,
            source_id=t.source_id,
            source_name=t.source_name,
            source_type=t.source_type,
            status=t.status,
            articles_found=t.articles_found,
            error_msg=t.error_msg,
            steps=_json.loads(t.steps or "[]"),
            started_at=_iso(t.started_at),
            finished_at=_iso(t.finished_at),
        )
        for t in logs
    ]


@router.get("/scheduler", response_model=List[dict])
def scheduler_status():
    return get_scheduler_status()


