"""
Ticker alias dictionary: maps alternative names/abbreviations to canonical tickers.

Keys are lowercase strings. Matching is done case-insensitively with word boundaries
so short aliases like "NV" don't fire inside longer words like "NVIDIA".

For leveraged/inverse ETFs (NVDL, SOXL, etc.) we keep them as separate tickers
rather than folding them into the underlying — they're independently tradeable assets
and bloggers track them distinctly.
"""

from __future__ import annotations

import re

# ── Alias table ───────────────────────────────────────────────────────────────
# Format: "alias (lowercase)" -> "CANONICAL_TICKER"
# Add entries freely; duplicates are harmless.

ALIASES: dict[str, str] = {
    # ── NVIDIA / NVDA ─────────────────────────────────────────────────────────
    "nvidia":   "NVDA",
    "英伟达":   "NVDA",
    "nv":       "NVDA",   # matched as whole word only

    # ── Apple / AAPL ──────────────────────────────────────────────────────────
    "apple":    "AAPL",
    "苹果":     "AAPL",

    # ── Tesla / TSLA ──────────────────────────────────────────────────────────
    "tesla":    "TSLA",
    "特斯拉":   "TSLA",

    # ── Microsoft / MSFT ──────────────────────────────────────────────────────
    "microsoft": "MSFT",
    "微软":      "MSFT",

    # ── Amazon / AMZN ─────────────────────────────────────────────────────────
    "amazon":   "AMZN",
    "亚马逊":   "AMZN",

    # ── Alphabet / GOOGL ──────────────────────────────────────────────────────
    "google":   "GOOGL",
    "alphabet": "GOOGL",
    "谷歌":     "GOOGL",

    # ── Meta / META ───────────────────────────────────────────────────────────
    "meta":     "META",

    # ── Rocket Lab / RKLB ─────────────────────────────────────────────────────
    "rocket lab":        "RKLB",
    "rocketlab":         "RKLB",
    "火箭实验室":         "RKLB",

    # ── SpaceX / SATS ─────────────────────────────────────────────────────────
    "spacex":   "SATS",   # SATS is the main SpaceX-linked public vehicle

    # ── Palantir / PLTR ───────────────────────────────────────────────────────
    "palantir": "PLTR",

    # ── Broadcom / AVGO ───────────────────────────────────────────────────────
    "broadcom": "AVGO",
    "博通":     "AVGO",

    # ── Taiwan Semiconductor / TSM ────────────────────────────────────────────
    "tsmc":     "TSM",
    "台积电":   "TSM",

    # ── Lumentum / LITE ───────────────────────────────────────────────────────
    "lumentum": "LITE",

    # ── Cerebras / CBRS ───────────────────────────────────────────────────────
    "cerebras": "CBRS",

    # ── Nebius / NBIS ─────────────────────────────────────────────────────────
    "nebius":   "NBIS",

    # ── CoreWeave / CRWV ──────────────────────────────────────────────────────
    "coreweave": "CRWV",

    # ── Index ETFs ────────────────────────────────────────────────────────────
    "标普":     "SPY",
    "纳指":     "QQQ",
    "纳斯达克": "QQQ",
}

# Pre-compile patterns for each alias (word-boundary aware, case-insensitive)
# Chinese characters don't have ASCII word boundaries so we use lookahead/behind.
_COMPILED: list[tuple[re.Pattern, str]] = []

for _alias, _ticker in ALIASES.items():
    if re.search(r"[^\x00-\x7f]", _alias):
        # Chinese / non-ASCII: just substring match (Chinese text has no spaces between words)
        _pat = re.compile(re.escape(_alias))
    else:
        # ASCII: wrap in word boundaries
        _pat = re.compile(r"\b" + re.escape(_alias) + r"\b", re.IGNORECASE)
    _COMPILED.append((_pat, _ticker))


def extract_tickers_from_aliases(text: str) -> list[str]:
    """Return tickers found via the alias dictionary (no $ prefix needed)."""
    found: set[str] = set()
    for pattern, ticker in _COMPILED:
        if pattern.search(text):
            found.add(ticker)
    return list(found)
