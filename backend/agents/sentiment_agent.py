from __future__ import annotations

import json
import logging
from typing import List

from langchain.schema import HumanMessage, SystemMessage

from agents.base import get_llm, get_active_prompt
from services.source_labels import format_daily_blocks_by_source, normalize_sentiment_sources

logger = logging.getLogger(__name__)

# 与用户库 Prompt 拼接：强制 source_sentiments 仅包含有操作/观点的来源
_SOURCE_SENTIMENT_FILTER = """

【source_sentiments 硬性规则】
- 仅为满足以下任一条件的【】数据源生成一条记录（source 必须与【】内名称完全一致）：
  (1) 明确交易操作：买卖、加减仓、开平仓、期权操作、止损止盈、仓位或标的变动等；
  (2) 明确投研观点：对大盘/板块/个股的多空判断或可执行看法（非纯新闻复述）。
- 以下内容不得单独为某来源生成条目：纯广告、加群引流、客服/邮箱/链接推广、无关闲聊、仅转载而无观点。
- summary 用 1～2 句概括「今日操作与观点」，不要抄邮箱、电话、促销语。若某来源全日无可摘录操作与观点，则不要出现在 source_sentiments 中。
- 整体情绪字段 overall_score / label / bull_ratio 等仍针对全市场；source_sentiments 宁可少不要滥。
"""


def run_sentiment_agent(
    date: str,
    daily_texts: List[str] | None = None,
    daily_by_source: dict[str, list[str]] | None = None,
) -> dict:
    """
    Analyse market sentiment from today's daily digest only (简讯时间窗内正文).
    When daily_by_source is set, each snippet is labeled with 【Source.name】 from DB
    so source_sentiments use configured names. Does not use RAG.
    """
    system_prompt = get_active_prompt("sentiment_agent") or ""

    canonical_names: list[str] = []
    if daily_by_source and any((k or "").strip() for k in daily_by_source):
        daily_block = format_daily_blocks_by_source(daily_by_source)
        canonical_names = sorted({k.strip() for k in daily_by_source if k and k.strip()})
    elif daily_texts:
        daily_block = "\n\n---\n\n".join(t[:300] for t in daily_texts[:40])
    else:
        daily_block = ""

    if not daily_block:
        logger.warning("No daily digest text for sentiment analysis on %s", date)
        return {
            "overall_score": 0.0,
            "label": "中性",
            "bull_ratio": 0.5,
            "bear_ratio": 0.5,
            "key_reasons": ["当日无有效内容"],
            "source_sentiments": [],
        }

    naming_hint = ""
    if canonical_names:
        naming_hint = (
            "\n\n（每条简讯开头的【】内为后台「数据源」配置名称；"
            "source_sentiments 中 source 必须与之一字不差地对应，勿用推特昵称或自拟称呼。）"
        )

    user_message = f"日期：{date}\n\n以下是今日简讯内容：\n\n{daily_block}{naming_hint}"

    llm = get_llm(temperature=0.1)
    response = llm.invoke(
        [
            SystemMessage(content=(system_prompt or "") + _SOURCE_SENTIMENT_FILTER),
            HumanMessage(content=user_message),
        ]
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
    if canonical_names:
        result["source_sentiments"] = normalize_sentiment_sources(
            result.get("source_sentiments"), canonical_names
        )
    return result
