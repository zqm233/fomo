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
_DEFAULT_RSS_ITEM_COUNT = 10

_RENDER_WAKE_MARKERS = (
    b"welcome to render",
    b"application loading",
    b"service waking up",
)


def _uses_rsshub_limit(url: str) -> bool:
    """仅 RSSHub 识别 ``limit``；公众号等带 token 的源不能改 query，否则会 403。"""
    host = urlparse(url).netloc.lower()
    return host.endswith(".onrender.com") or "rsshub" in host


def _feed_url_with_rsshub_limit(url: str, limit: int) -> str:
    """在 query 里写入 ``limit=<n>``（覆盖已有同名参数），RSSHub 会按此限制条目数。"""
    p = urlparse(url)
    pairs = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k != "limit"]
    pairs.append(("limit", str(limit)))
    query = urlencode(pairs)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, query, p.fragment))


def _resolve_fetch_url(url: str, limit: int) -> str:
    if _uses_rsshub_limit(url):
        return _feed_url_with_rsshub_limit(url, limit)
    return url


def _rss_request_headers(url: str) -> dict[str, str]:
    p = urlparse(url)
    origin = f"{p.scheme}://{p.netloc}"
    return {
        "User-Agent": _RSS_FETCH_UA,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US,en;q=0.8",
        "Referer": f"{origin}/",
        "Origin": origin,
    }


def _redact_url_for_log(url: str) -> str:
    p = urlparse(url)
    if not p.query:
        return url
    pairs = []
    for k, v in parse_qsl(p.query, keep_blank_values=True):
        if k.lower() in ("token", "key", "api_key", "apikey", "k"):
            pairs.append((k, "***"))
        else:
            pairs.append((k, v))
    query = urlencode(pairs)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, query, p.fragment))


def _format_http_error(status_code: int, content_type: str, body: bytes) -> str:
    base = f"拉取 RSS 失败: HTTP {status_code}"
    if content_type:
        base += f" ({content_type})"
    snippet = (body or b"")[:500].decode("utf-8", errors="replace").strip()
    if snippet and "json" in (content_type or "").lower():
        base += f" — {snippet[:200]}"
    elif status_code == 403 and (b"cloudflare" in (body or b"").lower() or "html" in (content_type or "").lower()):
        base += " — 可能被 CDN 拦截（云主机 IP）。本地网络可试；或自托管 WeChat RSS"
    elif status_code in (401, 403):
        base += " — 请检查订阅链接里的 token 是否有效、未过期"
    return base


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).digest().hex()


_BLOCK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "section", "hr"}


def _clean_html(raw: str) -> str:
    """Convert HTML (including WeChat mdnice editor output) to clean plain text."""
    if not raw:
        return ""

    soup = BeautifulSoup(raw, "lxml")

    for tag in soup.find_all(_BLOCK_TAGS):
        tag.insert_before("\n")
        tag.append("\n")

    text = soup.get_text(separator="")
    text = html.unescape(text)

    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
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


def _is_render_wake_page(payload: bytes, content_type: str) -> bool:
    if not payload:
        return False
    head = payload[:8192].lower()
    if any(marker in head for marker in _RENDER_WAKE_MARKERS):
        return True
    ctype = (content_type or "").lower()
    return "html" in ctype and b"<rss" not in head and b"<feed" not in head


class RssCrawlResult:
    def __init__(self, articles: list[dict], error: Optional[str] = None):
        self.articles = articles
        self.error = error
        self.success = error is None


def crawl_rss(feed_url: str, count: int = _DEFAULT_RSS_ITEM_COUNT) -> RssCrawlResult:
    """
    Fetch and parse an RSS / Atom feed.
    Returns articles as dicts with keys: content, url, author, published_at, content_hash.

    抓取前会做 URL strip。仅 RSSHub 类地址会追加 ``limit``；公众号等 token 链接保持原样。
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

    fetch_url = _resolve_fetch_url(normalized, effective_count)

    payload: bytes | None = None
    ctype: str = ""
    final_url = fetch_url

    headers = _rss_request_headers(fetch_url)

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
            logger.warning(
                "RSS HTTP error host=%s status=%s url=%s",
                urlparse(final_url).netloc,
                r.status_code,
                _redact_url_for_log(final_url),
            )
            return RssCrawlResult(
                articles=[],
                error=_format_http_error(r.status_code, ctype, r.content or b""),
            )
        payload = r.content or b""
    except requests.RequestException as e:
        return RssCrawlResult(articles=[], error=f"拉取 RSS 失败: {e}")

    if not payload or not payload.strip():
        return RssCrawlResult(articles=[], error="RSS 正文为空")

    if _is_render_wake_page(payload, ctype):
        return RssCrawlResult(
            articles=[],
            error="RSSHub 仍在启动（Render 冷启动），请稍后再试一次拉取",
        )

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

        raw_html = ""
        if entry.get("content"):
            raw_html = entry["content"][0].get("value", "")
        elif entry.get("summary"):
            raw_html = entry.get("summary", "")

        body = _clean_html(raw_html)

        if body:
            norm_title = re.sub(r"\s+", "", title[:40])
            norm_body = re.sub(r"\s+", "", body[:40])
            content = body if norm_title == norm_body else f"{title}\n\n{body}"
        else:
            content = title
        content = content[:12000]

        if not content.strip() or not url:
            continue

        author = entry.get("author", feed.feed.get("title", final_url)).strip()
        published_at = _parse_date(entry)

        articles.append({
            "content": content,
            "url": url,
            "author": author,
            "published_at": published_at,
            "content_hash": _sha256(url),
        })

    log_host = urlparse(final_url).netloc or "(unknown-host)"
    logger.info(
        "Crawled %d articles from RSS host=%s url=%s bytes=%s",
        len(articles),
        log_host,
        _redact_url_for_log(final_url),
        len(payload) if payload is not None else 0,
    )
    return RssCrawlResult(articles=articles)
