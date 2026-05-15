from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Report

router = APIRouter()


class ReportOut(BaseModel):
    id: str
    report_date: str
    report_type: str
    sentiment: dict
    hotspots: dict
    stock_prices: dict
    summary_text: str
    article_count: int
    created_at: str


def _to_out(r: Report) -> ReportOut:
    return ReportOut(
        id=r.id,
        report_date=r.report_date,
        report_type=r.report_type,
        sentiment=json.loads(r.sentiment_json),
        hotspots=json.loads(r.hotspots_json),
        stock_prices=json.loads(r.stock_prices_json),
        summary_text=r.summary_text,
        article_count=r.article_count,
        created_at=r.created_at.isoformat(),
    )


@router.get("", response_model=List[ReportOut])
def list_reports(
    report_type: Optional[str] = Query(None, description="'pre' | 'post'"),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(Report).order_by(Report.report_date.desc(), Report.report_type.desc())
    if report_type:
        q = q.filter(Report.report_type == report_type)
    return [_to_out(r) for r in q.limit(limit).all()]


@router.get("/latest", response_model=ReportOut)
def get_latest_report(
    report_type: str = Query("pre", description="'pre' | 'post'"),
    db: Session = Depends(get_db),
):
    report = (
        db.query(Report)
        .filter(Report.report_type == report_type)
        .order_by(Report.report_date.desc())
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="No report found")
    return _to_out(report)


@router.get("/{report_id}", response_model=ReportOut)
def get_report(report_id: str, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return _to_out(report)


@router.get("/by-date/{date}", response_model=List[ReportOut])
def get_reports_by_date(date: str, db: Session = Depends(get_db)):
    reports = db.query(Report).filter(Report.report_date == date).all()
    return [_to_out(r) for r in reports]
