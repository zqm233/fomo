from __future__ import annotations

import logging
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

engine = create_engine(
    settings.sqlite_url,
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(engine, "connect")
def _set_wal_mode(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    from db import models  # noqa: F401 – registers all ORM models

    Base.metadata.create_all(bind=engine)
    _seed_default_prompts()
    logger.info("Database initialised at %s", settings.sqlite_path)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _seed_default_prompts() -> None:
    """Insert default prompts for each agent if none exist yet."""
    from db.models import Prompt

    defaults = [
        (
            "sentiment_agent",
            """你是一位专业的美股市场情绪分析师。
根据以下今日推文/文章内容，分析整体市场情绪，输出 JSON 格式：
{
  "overall_score": <-1.0 ~ 1.0，正值看多负值看空>,
  "label": <"极度看多"|"看多"|"中性"|"看空"|"极度看空">,
  "bull_ratio": <看多比例 0~1>,
  "bear_ratio": <看空比例 0~1>,
  "key_reasons": [<最多3条核心理由>],
  "source_sentiments": [{"source": "博主名", "score": 0.0, "summary": "..."}]
}
只输出 JSON，不要额外说明。""",
        ),
        (
            "hotspot_agent",
            """你是一位美股市场热点分析师。
根据以下今日推文/文章内容，提取关键信息，输出 JSON 格式：
{
  "keywords": [<最多10个热门关键词>],
  "themes": [{"name": "主题名", "description": "简述", "mentions": <提及次数>}],
  "hot_tickers": [{"ticker": "AAPL", "context": "被提及原因"}],
  "events": [{"title": "事件名", "summary": "简述"}]
}
只输出 JSON，不要额外说明。""",
        ),
        (
            "summary_agent",
            """你是一位专业的美股投研简报撰写人。
根据以下信息生成结构化{report_type}简报，使用中文，Markdown 格式：

## 市场概览
（2-3句话总结当日市场）

## 情绪分析
（根据情绪数据描述多空分布）

## 热点主题
（列出3-5个核心主题和简析）

## 核心观点
（摘取博主/文章中最有价值的观点，注明来源）

## 重点标的
（结合股价数据点评热门个股）

## {outlook_label}
（前瞻性分析，2-3点）

要求：观点犀利，数据支撑，不超过800字。""",
        ),
        (
            "chat_agent",
            """你是 FOMO 投研助手，专注美股市场分析。
你的知识库包含财经博主的推文和公众号文章。
请基于检索到的相关内容回答用户问题，引用具体来源。
如果知识库中没有相关信息，如实说明，不要编造。
回答语言：用户用中文则中文回答，用英文则英文回答。""",
        ),
    ]

    db = SessionLocal()
    try:
        for agent_name, prompt_text in defaults:
            exists = db.query(Prompt).filter(Prompt.agent_name == agent_name).first()
            if not exists:
                db.add(
                    Prompt(
                        agent_name=agent_name,
                        prompt_text=prompt_text,
                        version=1,
                        is_active=True,
                    )
                )
        db.commit()
    finally:
        db.close()
