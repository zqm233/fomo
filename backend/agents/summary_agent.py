from __future__ import annotations

import logging
from typing import Dict, List

from langchain.schema import HumanMessage, SystemMessage

from agents.base import get_llm, get_active_prompt
from services.market import format_market_snapshot, format_stock_context

logger = logging.getLogger(__name__)

# Max articles shown per blogger in the per-source breakdown
_MAX_PER_SOURCE = 5
# Max chars per article snippet
_SNIPPET_LEN = 280


def _build_per_blogger_block(daily_by_source: Dict[str, List[str]]) -> str:
    """
    Format per-blogger content as structured blocks for the LLM.
    Each source gets its own section with up to _MAX_PER_SOURCE snippets.
    """
    if not daily_by_source:
        return "（暂无博主内容）"
    lines: list[str] = []
    for source_name, articles in daily_by_source.items():
        lines.append(f"### {source_name}（{len(articles)} 条）")
        for art in articles[:_MAX_PER_SOURCE]:
            snippet = art[:_SNIPPET_LEN].replace("\n", " ")
            lines.append(f"- {snippet}")
    return "\n".join(lines)


def run_summary_agent(
    date: str,
    report_type: str,
    sentiment: dict,
    hotspots: dict,
    stock_prices: dict,
    daily_texts: List[str] | None = None,
    daily_by_source: Dict[str, List[str]] | None = None,
    market_snapshot: dict | None = None,
) -> str:
    """
    Generate a structured pre/post market report in Markdown.

    Uses only: emotion/hotspot/stock snapshot passed in + daily digest excerpts
    (`daily_by_source`). Does not call RAG — research vectors are for
    chat Q&A only (`chat_agent`).
    """
    system_prompt = get_active_prompt("summary_agent") or ""

    outlook_label = "明日展望" if report_type == "post" else "今日关注"
    report_type_label = "盘后复盘" if report_type == "post" else "盘前简讯"

    _blogger_rules = """
【各博主章节硬性规则】
- 涉及博主/数据源的小节：只写当日简讯中能对应到的「交易操作」或「明确投资观点」。
- 禁止写入：客服邮箱、加群广告、与本日交易无关的闲聊、无观点的纯转载。
- 若某数据源全日无可摘录内容：不要为该来源起一行（可整体省略该小节中该人；若所有人皆无则可写一句：今日无可摘录的博主级操作与观点）。
- 详细原文由用户在「文章库」查看；此处只写提炼要点，勿堆砌无关摘录。
"""

    system_prompt = (system_prompt + _blogger_rules).format(
        report_type=report_type_label,
        outlook_label=outlook_label,
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
    per_blogger_block = _build_per_blogger_block(daily_by_source or {})

    # ── Post-market ────────────────────────────────────────────────────────────
    if report_type == "post":
        market_str = format_market_snapshot(market_snapshot or {})

        user_message = f"""请为 {date} 生成{report_type_label}。

## 今日市场行情
{market_str}

## 情绪分析
{sentiment_str}

## 当日热点主题
{themes_str or '暂无'}

## 热门关键词
{keywords_str or '暂无'}

## 热门标的
{tickers_str or '暂无'}

## 标的行情
{stock_context}

## 各博主今日内容（日常简讯来源，按博主分组）
以下是各博主在本次时间窗口内的内容原文，请从中提炼操作、观点和提及标的：

{per_blogger_block}

【命名约束】上一段每个「###」行首的名称即后台「数据源配置」中的名称。输出正文时凡提及博主/来源，必须使用这些名称（一字不差）；禁止使用推文里的昵称、@账号或自拟称呼。

请生成{report_type_label}，严格使用以下结构：

# {date} 美股盘后复盘简报

## 市场概览
（指数涨跌幅、整体情绪总结）

## 情绪分析
（多空比例、核心驱动因素）

## 热点主题
（今日主要投资主题，结合上方热点数据）

## 各博主操作与观点
（**仅列**当日有明确交易操作或可执行投资观点的数据源，名称与上文一致。**禁止**客服、加群、广告、无关闲聊；无操作无观点的博主**不要写**。全员无则本节食述一句）

## 核心观点
（综合各博主观点，提炼3-5条核心判断）

## {outlook_label}
（基于今日走势和博主观点的前瞻，明日值得关注的机会或风险）"""

    # ── Pre-market ─────────────────────────────────────────────────────────────
    else:
        user_message = f"""请为 {date} 生成{report_type_label}。

## 市场情绪（基于隔夜/凌晨内容）
{sentiment_str}

## 热点主题与宏观事件
{themes_str or '暂无'}

## 热门关键词
{keywords_str or '暂无'}

## 热门标的
{tickers_str or '暂无'}

## 隔夜期货/相关市场
{stock_context}

## 各博主隔夜及盘前内容（按博主分组）
以下是各博主在本时间窗口内的内容，请从中提炼观点和标的：

{per_blogger_block}

【命名约束】上一段每个「###」行首的名称即后台「数据源配置」中的名称。输出正文时凡提及博主/来源，必须使用这些名称（一字不差）；禁止使用推文里的昵称、@账号或自拟称呼。

请生成{report_type_label}，严格使用以下结构：

# {date} 美股盘前简讯

## 隔夜概况
（海外市场、期货、重要隔夜事件）

## 宏观与时政
（影响今日市场的政策、地缘、经济数据）

## 各博主盘前研判
（**仅列**有明确观点或操作的数据源；**禁止**广告与无关内容；无内容**不要写**该行）

## {outlook_label}
（今日开盘值得关注的标的、潜在催化剂和风险）"""

    llm = get_llm(temperature=0.5)
    response = llm.invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]
    )

    summary = response.content.strip()
    logger.info("Summary generated for %s %s (%d chars)", date, report_type, len(summary))
    return summary
