"""
AkShare 美股行情：仅使用新浪 stock_us_daily（前复权日线）。

实现细节在本模块；对外见 services.market。
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
from typing import Any, Dict, Iterator, List

from services.market.constants import DEFAULT_BENCHMARK_TICKERS, INDICES, SECTORS

logger = logging.getLogger(__name__)

_TICKER_PATTERN = re.compile(r"\$([A-Z]{1,5})\b")


def exception_log_detail(exc: BaseException) -> str:
    parts: list[str] = [type(exc).__name__]
    msg = str(exc).strip()
    if msg:
        parts.append(msg[:800])

    http_status = None
    resp = getattr(exc, "response", None)
    if resp is not None:
        http_status = getattr(resp, "status_code", None)
    if http_status is None:
        http_status = getattr(exc, "status_code", None)
    if http_status is not None:
        parts.append(f"http_status={http_status}")

    if isinstance(exc, OSError) and exc.errno is not None:
        parts.append(f"errno={exc.errno}")

    chain = exc.__cause__
    if chain is None:
        chain = getattr(exc, "__context__", None)
    if chain is not None:
        parts.append(f"chain={type(chain).__name__}")
        cmsg = str(chain).strip()
        if cmsg:
            parts.append(cmsg[:400])
        if isinstance(chain, OSError) and chain.errno is not None:
            parts.append(f"chain_errno={chain.errno}")

    return " | ".join(parts)


@contextlib.contextmanager
def without_proxy_env() -> Iterator[None]:
    """Strip proxy-related env for AkShare HTTP; restore after block."""
    saved: dict[str, str] = {}
    try:
        for key in list(os.environ.keys()):
            if "proxy" in key.lower():
                saved[key] = os.environ.pop(key)
        os.environ["NO_PROXY"] = "*"
        os.environ["no_proxy"] = "*"
        yield
    finally:
        for k in ("NO_PROXY", "no_proxy"):
            os.environ.pop(k, None)
        os.environ.update(saved)


def normalize_symbol(sym: str) -> str | None:
    s = sym.strip().upper()
    if not s or s.startswith("^"):
        return None
    return s


def display_name(sym: str) -> str:
    if sym in INDICES:
        return INDICES[sym]
    if sym in SECTORS:
        return SECTORS[sym]
    return sym


def _fetch_closes_us_daily(ak: Any, sym: str, days: int) -> list[float]:
    df = ak.stock_us_daily(symbol=sym.upper(), adjust="qfq")
    if df is None or df.empty or "close" not in df.columns:
        return []
    closes = [round(float(v), 4) for v in df["close"].dropna().tolist()]
    if not closes:
        return []
    return closes[-(days + 2):]


def fetch_closes_for_symbol(ak: Any, sym: str, days: int) -> list[float]:
    with without_proxy_env():
        try:
            daily = _fetch_closes_us_daily(ak, sym, days)
            if daily:
                return daily
        except Exception as e:
            logger.debug(
                "stock_us_daily failed %s: %s",
                sym,
                exception_log_detail(e),
            )
    return []


def batch_fetch_closes(symbols: list[str], days: int) -> dict[str, list[float]]:
    if not symbols:
        return {}
    import akshare as ak

    result: dict[str, list[float]] = {}
    for raw in symbols:
        sym = normalize_symbol(raw)
        if not sym:
            continue
        closes = fetch_closes_for_symbol(ak, sym, days=days)
        if closes:
            result[sym] = closes
    logger.info("US daily closes (Sina): %d/%d symbols", len(result), len(symbols))
    return result


def extract_tickers_from_text(texts: list[str]) -> list[str]:
    from services.ticker_aliases import extract_tickers_from_aliases

    found: set[str] = set()
    for text in texts:
        for match in _TICKER_PATTERN.finditer(text):
            found.add(match.group(1))
        found.update(extract_tickers_from_aliases(text))
    return list(found)


def fetch_stock_prices(tickers: List[str]) -> Dict[str, dict]:
    want = {normalize_symbol(t) for t in tickers}
    want.discard(None)
    all_symbols = list(set(DEFAULT_BENCHMARK_TICKERS) | want)

    import akshare as ak

    result: dict[str, dict] = {}

    for sym in all_symbols:
        if not sym:
            continue
        closes = fetch_closes_for_symbol(ak, sym, days=2)
        if len(closes) >= 2:
            price = closes[-1]
            change_pct = (closes[-1] - closes[-2]) / closes[-2] * 100
            result[sym] = {
                "symbol": sym,
                "price": round(price, 2),
                "change_pct": round(change_pct, 2),
                "name": display_name(sym),
            }

    return result


def fetch_ticker_history(tickers: List[str], period: str = "7d") -> Dict[str, dict]:
    if not tickers:
        return {}
    days = int(period.rstrip("d")) if period.endswith("d") else 7

    order: list[tuple[str, str]] = []
    seen_norm: set[str] = set()
    for raw in tickers:
        n = normalize_symbol(raw)
        if not n or n in seen_norm:
            continue
        seen_norm.add(n)
        order.append((raw, n))

    norm = [b for _, b in order]
    closes_map = batch_fetch_closes(norm, days=days)

    out: dict[str, dict] = {}
    for raw_sym, sym in order:
        closes = closes_map.get(sym, [])
        if not closes:
            continue
        price = closes[-1]
        change_pct = (
            (closes[-1] - closes[0]) / closes[0] * 100 if closes[0] else 0.0
        )
        out[raw_sym] = {
            "symbol": sym,
            "name": display_name(sym),
            "price": round(price, 2),
            "change_pct": round(change_pct, 2),
            "sparkline": closes,
        }
    return out


def fetch_market_snapshot() -> dict:
    snapshot: dict = {"indices": {}, "sectors": {}}

    def fill(label_map: dict[str, str], bucket: str) -> None:
        for symbol, label in label_map.items():
            closes = batch_fetch_closes([symbol], days=2).get(symbol, [])
            if len(closes) >= 2:
                snapshot[bucket][label] = {
                    "symbol": symbol,
                    "close": round(closes[-1], 2),
                    "change_pct": round(
                        (closes[-1] - closes[-2]) / closes[-2] * 100, 2
                    ),
                }

    fill(INDICES, "indices")
    fill(SECTORS, "sectors")

    logger.info(
        "Market snapshot: %d indices, %d sectors",
        len(snapshot["indices"]),
        len(snapshot["sectors"]),
    )
    return snapshot
