"""将简报链路中的「博主 / 数据源」与后台 Source.name 对齐。"""

from __future__ import annotations

import difflib
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def format_daily_blocks_by_source(
    daily_by_source: dict[str, list[str]],
    *,
    max_snippets: int = 48,
    snippet_len: int = 300,
) -> str:
    """
    每条简讯前加【数据源配置名称】，便于 LLM 在 source_sentiments 等处复用同一套名称。
    """
    parts: list[str] = []
    n = 0
    names = sorted(
        (k for k in daily_by_source.keys() if (k or "").strip()),
        key=lambda x: x,
    )
    for name in names:
        for text in daily_by_source[name]:
            if n >= max_snippets:
                return "\n\n---\n\n".join(parts)
            body = (text or "")[:snippet_len]
            parts.append(f"【{name.strip()}】\n{body}")
            n += 1
    return "\n\n---\n\n".join(parts)


_WS_RE = re.compile(r"\s+")


def _norm_key(s: str) -> str:
    return _WS_RE.sub("", (s or "").strip().lower())


def normalize_sentiment_sources(
    source_sentiments: list[dict[str, Any]] | None,
    allowed_names: list[str],
) -> list[dict[str, Any]]:
    """
    将 LLM 返回的 source 字段对齐到数据源配置名（Source.name）。
    无法对齐的条目丢弃，避免界面出现推特昵称等随机称呼。
    """
    if not source_sentiments:
        return []
    allowed = [a.strip() for a in allowed_names if a and str(a).strip()]
    if not allowed:
        return [x for x in source_sentiments if isinstance(x, dict)]

    allowed_set = set(allowed)
    norm_to_canonical = {_norm_key(a): a for a in allowed}

    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in source_sentiments:
        if not isinstance(item, dict):
            continue
        raw = (item.get("source") or "").strip()
        if not raw:
            continue

        chosen: str | None = None
        if raw in allowed_set:
            chosen = raw
        else:
            nk = _norm_key(raw)
            if nk in norm_to_canonical:
                chosen = norm_to_canonical[nk]
        if chosen is None and len(raw) >= 2:
            for a in allowed:
                if len(a) >= 2 and (raw in a or a in raw):
                    chosen = a
                    break
            if chosen is None:
                fuzzy = difflib.get_close_matches(raw, allowed, n=1, cutoff=0.55)
                if fuzzy:
                    chosen = fuzzy[0]

        if not chosen:
            logger.debug("Drop source_sentiments row: unknown source %r", raw[:80])
            continue
        if chosen in seen:
            continue
        seen.add(chosen)
        out.append({**item, "source": chosen})

    return out
