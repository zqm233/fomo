from __future__ import annotations

import json
import logging
from typing import List

from langchain.schema import HumanMessage, SystemMessage

from agents.base import get_llm, get_active_prompt
from tools.rag_tool import rag_search

logger = logging.getLogger(__name__)


def run_sentiment_agent(
    source_ids: List[str],
    date: str,
) -> dict:
    """
    Analyse market sentiment from today's content.
    Returns structured sentiment dict.
    """
    system_prompt = get_active_prompt("sentiment_agent") or ""

    docs = rag_search(
        query="市场多空情绪 股市看法 风险 机会",
        source_ids=source_ids,
        n_results=20,
        date_filter=date,
    )

    if not docs:
        logger.warning("No documents found for sentiment analysis on %s", date)
        return {
            "overall_score": 0.0,
            "label": "中性",
            "bull_ratio": 0.5,
            "bear_ratio": 0.5,
            "key_reasons": ["当日无有效内容"],
            "source_sentiments": [],
        }

    content_block = "\n\n---\n\n".join(
        f"[{d['metadata'].get('author', d['source_id'])}] {d['content'][:400]}"
        for d in docs
    )
    user_message = f"日期：{date}\n\n以下是今日内容：\n\n{content_block}"

    llm = get_llm(temperature=0.1)
    response = llm.invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]
    )

    raw = response.content.strip()
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        result = json.loads(raw[start:end])
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Failed to parse sentiment JSON: %s\nRaw: %s", e, raw[:300])
        result = {
            "overall_score": 0.0,
            "label": "中性",
            "bull_ratio": 0.5,
            "bear_ratio": 0.5,
            "key_reasons": ["解析失败"],
            "source_sentiments": [],
        }

    logger.info("Sentiment analysis complete for %s: %s", date, result.get("label"))
    return result
