from __future__ import annotations

import hashlib
import html
import io
import logging
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import feedparser
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# RSSHub / CDN 对部分非浏览器 UA 会限流或直接断连；抓取显式使用常见浏览器 UA
_RSS_FETCH_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
_FETCH_TIMEOUT_SEC = (15, 75)  # connect, read — 外层 pipeline 有约 90s 上限 / 源
# RSSHub：在请求 URL 上带 `limit` 可少拉条目、减轻负载；与本地下游截断保持一致
_DEFAULT_RSS_ITEM_COUNT = 10


def _feed_url_with_rsshub_limit(url: str, limit: int) -> str:
    """在 query 里写入 ``limit=<n>``（覆盖已有同名参数），RSSHub 会按此限制条目数。"""
    p = urlparse(url)
    pairs = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k != "limit"]
    pairs.append(("limit", str(limit)))
    query = urlencode(pairs)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, query, p.fragment))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).digest().hex()


_BLOCK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "section", "hr"}


def _clean_html(raw: str) -> str:
    """Convert HTML (including WeChat mdnice editor output) to clean plain text.

    Strategy:
    - Insert newlines before block-level tags so paragraphs are preserved
    - Strip all remaining tags and inline styles
    - Unescape HTML entities (&amp; &nbsp; etc.)
    - Collapse excessive blank lines
    """
    if not raw:
        return ""

    soup = BeautifulSoup(raw, "lxml")

    # Insert newline markers before block elements so we don't lose paragraph breaks
    for tag in soup.find_all(_BLOCK_TAGS):
        tag.insert_before("\n")
        tag.append("\n")

    text = soup.get_text(separator="")
    text = html.unescape(text)

    # Collapse runs of spaces/tabs on a single line
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    # Remove empty lines produced by pure-whitespace content, but keep single blank line between paragraphs
    cleaned: list[str] = []
    prev_blank = False
    for line in lines:
        if not line:
            if not prev_blank:
                cleaned.append("")
            prev_blank = True
        else:
            cleaned.append(line)
            prev_blank = False

    return "\n".join(cleaned).strip()


def _parse_date(entry) -> datetime:
    """Extract published date from a feedparser entry, falling back to now."""
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


class RssCrawlResult:
    def __init__(self, articles: list[dict], error: Optional[str] = None):
        self.articles = articles
        self.error = error
        self.success = error is None


def crawl_rss(feed_url: str, count: int = _DEFAULT_RSS_ITEM_COUNT) -> RssCrawlResult:
    """
    Fetch and parse an RSS / Atom feed.
    Returns articles as dicts with keys: content, url, author, published_at, content_hash.

    抓取前会做 URL strip；请求使用合并了 ``limit=<count>`` 的完整 URL（覆盖已有同名 query），默认 10。
    RSSHub 会据此限条数；其它源通常忽略未知的 ``limit`` 参数。
    """
    effective_count = max(1, min(count, 100))
    normalized = (feed_url or "").strip().strip("\ufeff")
    if not normalized:
        return RssCrawlResult(articles=[], error="RSS 地址为空")

    parsed_url = urlparse(normalized)
    if parsed_url.scheme.lower() not in ("http", "https"):
        return RssCrawlResult(
            articles=[],
            error="RSS 地址须以 http/https 开头（请勿在链接前多出空格或非 ASCII 符号）",
        )

    fetch_url = _feed_url_with_rsshub_limit(normalized, effective_count)

    payload: bytes | None = None
    ctype: str = ""
    final_url = fetch_url

    headers = {
        "User-Agent": _RSS_FETCH_UA,
        # 与 feedparser 默认一致：鼓励返回 XML/RSS，而非 HTML 占位页
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
    }

    try:
        r = requests.get(
            fetch_url,
            headers=headers,
            timeout=_FETCH_TIMEOUT_SEC,
            allow_redirects=True,
        )
        final_url = r.url
        ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip()
        if not r.ok:
            return RssCrawlResult(
                articles=[],
                error=(
                    f"拉取 RSS 失败: HTTP {r.status_code}"
                    + (f" ({ctype})" if ctype else "")
                ),
            )
        payload = r.content or b""
    except requests.RequestException as e:
        return RssCrawlResult(articles=[], error=f"拉取 RSS 失败: {e}")

    if not payload or not payload.strip():
        return RssCrawlResult(articles=[], error="RSS 正文为空")

    try:
        feed = feedparser.parse(
            io.BytesIO(payload),
            response_headers=dict(r.headers),
        )
    except Exception as e:
        return RssCrawlResult(articles=[], error=f"解析 RSS 失败: {e}")

    if feed.bozo and not feed.entries:
        reason = str(getattr(feed, "bozo_exception", "unknown"))
        return RssCrawlResult(articles=[], error=f"RSS 格式错误: {reason}")

    articles = []
    for entry in feed.entries[:effective_count]:
        title = entry.get("title", "").strip()
        url = entry.get("link", "").strip()

        # Content: prefer summary/content over title-only
        raw_html = ""
        if entry.get("content"):
            raw_html = entry["content"][0].get("value", "")
        elif entry.get("summary"):
            raw_html = entry.get("summary", "")

        body = _clean_html(raw_html)

        # RSSHub Twitter feeds use the tweet's first sentence as <title>,
        # so the body already contains the full text. Avoid duplicating it.
        if body:
            norm_title = re.sub(r"\s+", "", title[:40])
            norm_body  = re.sub(r"\s+", "", body[:40])
            content = body if norm_title == norm_body else f"{title}\n\n{body}"
        else:
            content = title
        content = content[:12000]  # chunker will split further; keep more context

        if not content.strip() or not url:
            continue

        author = entry.get("author", feed.feed.get("title", final_url)).strip()
        published_at = _parse_date(entry)

        articles.append({
            "content": content,
            "url": url,
            "author": author,
            "published_at": published_at,
            "content_hash": _sha256(url),  # hash URL, not full content
        })

    log_host = urlparse(final_url).netloc or "(unknown-host)"
    logger.info(
        "Crawled %d articles from RSS host=%s (final_url_scheme=%s status_bytes=%s)",
        len(articles),
        log_host,
        urlparse(final_url).scheme or "?",
        len(payload) if payload is not None else 0,
    )
    return RssCrawlResult(articles=articles)
