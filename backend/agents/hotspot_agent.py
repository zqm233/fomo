from __future__ import annotations

import json
import logging
from typing import List

from langchain.schema import HumanMessage, SystemMessage

from agents.base import get_llm, get_active_prompt
from services.source_labels import format_daily_blocks_by_source

logger = logging.getLogger(__name__)


def run_hotspot_agent(
    date: str,
    daily_texts: List[str] | None = None,
    daily_by_source: dict[str, list[str]] | None = None,
) -> dict:
    """
    Extract hot topics, keywords, tickers and events from today's daily digest only.
    When daily_by_source is provided, snippets are labeled with 【Source.name】.
    Does not read RAG / research vectors — that path is reserved for chat Q&A.
    """
    system_prompt = get_active_prompt("hotspot_agent") or ""

    if daily_by_source and any((k or "").strip() for k in daily_by_source):
        daily_block = format_daily_blocks_by_source(daily_by_source)
        naming_hint = (
            "\n\n（简讯均以【】标注后台数据源配置名称，分析时请沿用同一套名称指代来源。）"
        )
    elif daily_texts:
        daily_block = "\n\n---\n\n".join(t[:300] for t in daily_texts[:40])
        naming_hint = ""
    else:
        daily_block = ""
        naming_hint = ""

    if not daily_block:
        logger.warning("No daily digest text for hotspot analysis on %s", date)
        return {
            "keywords": [],
            "themes": [],
            "hot_tickers": [],
            "events": [],
        }

    user_message = f"日期：{date}\n\n以下是今日简讯内容：\n\n{daily_block}{naming_hint}"

    llm = get_llm(temperature=0.2)
    response = llm.invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]
    )

    raw = response.content.strip()
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        result = json.loads(raw[start:end])
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Failed to parse hotspot JSON: %s\nRaw: %s", e, raw[:300])
        result = {"keywords": [], "themes": [], "hot_tickers": [], "events": []}

    logger.info(
        "Hotspot analysis complete for %s: %d keywords, %d themes",
        date,
        len(result.get("keywords", [])),
        len(result.get("themes", [])),
    )
    return result
