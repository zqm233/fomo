"""US ETF labels for indices / sector snapshot (AkShare tickers)."""

from __future__ import annotations

from typing import Dict, Final

INDICES: Dict[str, str] = {
    "SPY": "标普500 (SPY)",
    "QQQ": "纳斯达克 (QQQ)",
    "DIA": "道琼斯 (DIA)",
    "IWM": "罗素2000 (IWM)",
}

SECTORS: Dict[str, str] = {
    "XLK": "科技",
    "XLF": "金融",
    "XLE": "能源",
    "XLC": "通信",
    "XLV": "医疗",
    "XLI": "工业",
    "XLY": "消费周期",
    "XLP": "消费必需",
    "XLB": "材料",
    "XLU": "公用事业",
    "XLRE": "房地产",
}

DEFAULT_BENCHMARK_TICKERS: Final[list[str]] = list(INDICES.keys())
