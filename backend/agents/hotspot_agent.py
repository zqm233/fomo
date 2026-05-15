from __future__ import annotations

import json
import logging
from typing import List

from langchain.schema import HumanMessage, SystemMessage

from agents.base import get_llm, get_active_prompt
from tools.rag_tool import rag_search

logger = logging.getLogger(__name__)


def run_hotspot_agent(
    source_ids: List[str],
    date: str,
) -> dict:
    """
    Extract hot topics, keywords, tickers and events from today's content.
    Returns structured hotspot dict.
    """
    system_prompt = get_active_prompt("hotspot_agent") or ""

    docs = rag_search(
        query="热门话题 重要事件 股票 个股 板块 主题",
        source_ids=source_ids,
        n_results=20,
        date_filter=date,
    )

    if not docs:
        logger.warning("No documents found for hotspot analysis on %s", date)
        return {
            "keywords": [],
            "themes": [],
            "hot_tickers": [],
            "events": [],
        }

    content_block = "\n\n---\n\n".join(
        f"[{d['metadata'].get('author', d['source_id'])}] {d['content'][:400]}"
        for d in docs
    )
    user_message = f"日期：{date}\n\n以下是今日内容：\n\n{content_block}"

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
