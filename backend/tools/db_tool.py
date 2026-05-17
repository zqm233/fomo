from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from db.database import SessionLocal
from db.models import Report

logger = logging.getLogger(__name__)


class DBWriteInput(BaseModel):
    operation: str = Field(description="操作类型: 'save_report'")
    data: Dict[str, Any] = Field(description="要写入的数据")


class DBReadInput(BaseModel):
    operation: str = Field(description="操作类型: 'get_report' | 'list_reports'")
    params: Dict[str, Any] = Field(default_factory=dict, description="查询参数")


class DBWriteTool(BaseTool):
    """DB 写入工具 - Agent 用于保存分析结果"""

    name: str = "db_write"
    description: str = "将分析结果写入数据库，支持保存简报数据。"
    args_schema: type[BaseModel] = DBWriteInput

    def _run(self, operation: str, data: Dict[str, Any]) -> str:
        if operation == "save_report":
            return _save_report(data)
        return f"未知操作: {operation}"

    async def _arun(self, *args, **kwargs) -> str:
        return self._run(*args, **kwargs)


class DBReadTool(BaseTool):
    """DB 读取工具 - Agent 用于查询历史数据"""

    name: str = "db_read"
    description: str = "从数据库读取历史简报或配置数据。"
    args_schema: type[BaseModel] = DBReadInput

    def _run(self, operation: str, params: Dict[str, Any]) -> str:
        if operation == "get_report":
            return _get_report(params.get("date", ""), params.get("type", "pre"))
        if operation == "list_reports":
            return _list_reports(params.get("limit", 10))
        return f"未知操作: {operation}"

    async def _arun(self, *args, **kwargs) -> str:
        return self._run(*args, **kwargs)


def _save_report(data: dict) -> str:
    db = SessionLocal()
    try:
        report_date = data.get("report_date", "")
        report_type = data.get("report_type", "pre")
        existing = (
            db.query(Report)
            .filter(Report.report_date == report_date, Report.report_type == report_type)
            .first()
        )
        digest = data.get("source_digest") or []
        digest_json = json.dumps(digest, ensure_ascii=False)
        hot_pool = data.get("hot_pool") or []
        hot_pool_json = json.dumps(hot_pool, ensure_ascii=False)
        if existing:
            existing.sentiment_json = json.dumps(data.get("sentiment", {}), ensure_ascii=False)
            existing.hotspots_json = json.dumps(data.get("hotspots", {}), ensure_ascii=False)
            existing.stock_prices_json = json.dumps(data.get("stock_prices", {}), ensure_ascii=False)
            existing.summary_text = data.get("summary_text", "")
            existing.article_count = data.get("article_count", 0)
            existing.source_digest_json = digest_json
            existing.hot_pool_json = hot_pool_json
            report_id = existing.id
        else:
            report = Report(
                report_date=report_date,
                report_type=report_type,
                sentiment_json=json.dumps(data.get("sentiment", {}), ensure_ascii=False),
                hotspots_json=json.dumps(data.get("hotspots", {}), ensure_ascii=False),
                stock_prices_json=json.dumps(data.get("stock_prices", {}), ensure_ascii=False),
                summary_text=data.get("summary_text", ""),
                article_count=data.get("article_count", 0),
                source_digest_json=digest_json,
                hot_pool_json=hot_pool_json,
            )
            db.add(report)
            report_id = report.id
        db.commit()
        return f"简报已保存，ID: {report_id}"
    except Exception as e:
        db.rollback()
        logger.error("Failed to save report: %s", e)
        return f"保存失败: {e}"
    finally:
        db.close()


def _get_report(date: str, report_type: str) -> str:
    db = SessionLocal()
    try:
        report = (
            db.query(Report)
            .filter(Report.report_date == date, Report.report_type == report_type)
            .first()
        )
        if not report:
            return f"未找到 {date} {report_type} 简报"
        return json.dumps(
            {
                "id": report.id,
                "report_date": report.report_date,
                "report_type": report.report_type,
                "summary_text": report.summary_text,
                "sentiment": json.loads(report.sentiment_json),
                "hotspots": json.loads(report.hotspots_json),
            },
            ensure_ascii=False,
        )
    finally:
        db.close()


def _list_reports(limit: int) -> str:
    db = SessionLocal()
    try:
        reports = (
            db.query(Report)
            .order_by(Report.report_date.desc(), Report.report_type.desc())
            .limit(limit)
            .all()
        )
        result = [
            {"id": r.id, "date": r.report_date, "type": r.report_type, "article_count": r.article_count}
            for r in reports
        ]
        return json.dumps(result, ensure_ascii=False)
    finally:
        db.close()


def save_report_direct(data: dict) -> str:
    """Convenience function for direct use in pipeline."""
    return _save_report(data)


def get_db_tools() -> tuple[DBWriteTool, DBReadTool]:
    return DBWriteTool(), DBReadTool()
