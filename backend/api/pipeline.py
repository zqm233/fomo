from __future__ import annotations

import threading
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import PipelineRun
from scheduler.tasks import get_scheduler_status

router = APIRouter()


class TriggerRequest(BaseModel):
    report_type: str = "pre"  # "pre" | "post" | "manual"


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
        started_at=run.started_at.isoformat() if run.started_at else None,
        finished_at=run.finished_at.isoformat() if run.finished_at else None,
        error_msg=run.error_msg,
        articles_crawled=run.articles_crawled,
        created_at=run.created_at.isoformat(),
    )


def _run_async(job_id: str, report_type: str):
    from pipeline.daily_pipeline import run_pipeline
    run_pipeline(report_type=report_type, job_id=job_id)


@router.post("/trigger", response_model=TriggerResponse)
def trigger_pipeline(body: TriggerRequest, db: Session = Depends(get_db)):
    job_id = str(uuid.uuid4())

    run = PipelineRun(job_id=job_id, run_type=body.report_type, status="queued")
    db.add(run)
    db.commit()

    thread = threading.Thread(
        target=_run_async,
        args=(job_id, body.report_type),
        daemon=True,
    )
    thread.start()

    return TriggerResponse(job_id=job_id, message="流水线已启动，请通过 job_id 轮询状态")


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


@router.get("/scheduler", response_model=List[dict])
def scheduler_status():
    return get_scheduler_status()
