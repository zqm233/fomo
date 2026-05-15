from __future__ import annotations

import logging
from typing import List

from langchain.schema import HumanMessage, SystemMessage

from agents.base import get_llm, get_active_prompt
from tools.rag_tool import rag_search
from services.stock_price import format_stock_context

logger = logging.getLogger(__name__)


def run_summary_agent(
    source_ids: List[str],
    date: str,
    report_type: str,
    sentiment: dict,
    hotspots: dict,
    stock_prices: dict,
) -> str:
    """
    Generate a structured pre/post market report in Markdown.
    Returns the summary text.
    """
    system_prompt = get_active_prompt("summary_agent") or ""

    outlook_label = "明日展望" if report_type == "post" else "今日关注"
    report_type_label = "盘后复盘" if report_type == "post" else "盘前简讯"

    system_prompt = system_prompt.format(
        report_type=report_type_label,
        outlook_label=outlook_label,
    )

    support_docs = rag_search(
        query="核心观点 市场分析 重要判断",
        source_ids=source_ids,
        n_results=10,
        date_filter=date,
    )

    quotes_block = "\n\n".join(
        f"- **{d['metadata'].get('author', '未知')}**: {d['content'][:200]}"
        for d in support_docs[:6]
    )

    sentiment_str = (
        f"整体情绪：{sentiment.get('label', '中性')}（评分 {sentiment.get('overall_score', 0):.1f}）\n"
        f"看多比例：{sentiment.get('bull_ratio', 0.5) * 100:.0f}%  "
        f"看空比例：{sentiment.get('bear_ratio', 0.5) * 100:.0f}%\n"
        f"核心原因：{', '.join(sentiment.get('key_reasons', []))}"
    )

    themes_str = "\n".join(
        f"- {t['name']}: {t['description']}"
        for t in hotspots.get("themes", [])[:5]
    )
    keywords_str = "、".join(hotspots.get("keywords", [])[:10])
    tickers_str = "、".join(
        f"${t['ticker']}" for t in hotspots.get("hot_tickers", [])[:5]
    )

    stock_context = format_stock_context(stock_prices)

    user_message = f"""请为 {date} 生成{report_type_label}简报。

## 情绪分析结果
{sentiment_str}

## 热点主题
{themes_str or '暂无'}

## 热门关键词
{keywords_str or '暂无'}

## 热门标的
{tickers_str or '暂无'}

## 市场行情
{stock_context}

## 博主核心观点摘录
{quotes_block or '暂无引用'}

请根据以上信息生成完整简报。"""

    llm = get_llm(temperature=0.5)
    response = llm.invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]
    )

    summary = response.content.strip()
    logger.info("Summary generated for %s %s (%d chars)", date, report_type, len(summary))
    return summary
