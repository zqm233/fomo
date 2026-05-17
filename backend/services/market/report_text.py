"""Format stock / market snapshots for LLM prompts."""

from __future__ import annotations

from typing import Dict


def format_stock_context(prices: Dict[str, dict]) -> str:
    if not prices:
        return "（暂无股价数据）"
    lines = ["当日主要市场表现："]
    for sym, d in prices.items():
        arrow = "▲" if d["change_pct"] >= 0 else "▼"
        sign = "+" if d["change_pct"] >= 0 else ""
        lines.append(
            f"  {sym} ({d['name']}): ${d['price']}  {arrow} {sign}{d['change_pct']:.2f}%"
        )
    return "\n".join(lines)


def format_market_snapshot(snapshot: dict) -> str:
    if not snapshot or (
        not snapshot.get("indices") and not snapshot.get("sectors")
    ):
        return "（市场数据暂不可用）"
    lines: list[str] = []
    if snapshot.get("indices"):
        lines.append("### 主要指数 ETF")
        for label, d in snapshot["indices"].items():
            sign = "+" if d["change_pct"] >= 0 else ""
            lines.append(f"- {label}: {d['close']:.2f}  {sign}{d['change_pct']:.2f}%")
    if snapshot.get("sectors"):
        lines.append("\n### 板块 ETF 涨跌（今日）")
        for label, d in sorted(
            snapshot["sectors"].items(),
            key=lambda x: x[1]["change_pct"],
            reverse=True,
        ):
            sign = "+" if d["change_pct"] >= 0 else ""
            lines.append(
                f"- {label}（{d['symbol']}）: {sign}{d['change_pct']:.2f}%"
            )
    return "\n".join(lines)
