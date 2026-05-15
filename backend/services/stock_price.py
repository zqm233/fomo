from __future__ import annotations

import logging
import re
from typing import Dict, List

import yfinance as yf

logger = logging.getLogger(__name__)

_DEFAULT_TICKERS = ["SPY", "QQQ", "DIA", "IWM"]

_TICKER_PATTERN = re.compile(r"\$([A-Z]{1,5})\b")


def extract_tickers_from_text(texts: List[str]) -> List[str]:
    """Extract $TICKER mentions from text list."""
    found = set()
    for text in texts:
        for match in _TICKER_PATTERN.finditer(text):
            found.add(match.group(1))
    return list(found)


def fetch_stock_prices(tickers: List[str]) -> Dict[str, dict]:
    """
    Fetch latest price data for given tickers via yfinance.
    Returns dict: ticker -> {price, change_pct, volume, name}
    """
    all_tickers = list(set(_DEFAULT_TICKERS + tickers))
    result: dict[str, dict] = {}

    for ticker_sym in all_tickers:
        try:
            ticker = yf.Ticker(ticker_sym)
            info = ticker.fast_info
            hist = ticker.history(period="2d")
            if hist.empty or len(hist) < 1:
                continue

            close_today = float(hist["Close"].iloc[-1])
            if len(hist) >= 2:
                close_prev = float(hist["Close"].iloc[-2])
                change_pct = (close_today - close_prev) / close_prev * 100
            else:
                change_pct = 0.0

            volume = int(hist["Volume"].iloc[-1]) if "Volume" in hist.columns else 0

            result[ticker_sym] = {
                "symbol": ticker_sym,
                "price": round(close_today, 2),
                "change_pct": round(change_pct, 2),
                "volume": volume,
                "name": getattr(info, "long_name", ticker_sym) or ticker_sym,
            }
        except Exception as e:
            logger.warning("Failed to fetch price for %s: %s", ticker_sym, e)

    return result


def format_stock_context(prices: Dict[str, dict]) -> str:
    """Format stock price data as context string for LLM prompts."""
    if not prices:
        return "（暂无股价数据）"

    lines = ["当日主要市场表现："]
    for sym, data in sorted(prices.items()):
        arrow = "▲" if data["change_pct"] >= 0 else "▼"
        color = "+" if data["change_pct"] >= 0 else ""
        lines.append(
            f"  {sym} ({data['name']}): ${data['price']}  {arrow} {color}{data['change_pct']:.2f}%"
        )
    return "\n".join(lines)
