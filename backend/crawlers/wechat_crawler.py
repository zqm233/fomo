from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

_SOGOU_API = "https://weixin.sogou.com/weixin"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).digest().hex()


def _clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return "\n".join(lines)


@retry(
    retry=retry_if_exception_type((requests.RequestException, RuntimeError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    reraise=True,
)
def _fetch_article(url: str) -> str:
    """Fetch and clean a WeChat article page."""
    cookie = settings.wechat_cookie
    headers = dict(_HEADERS)
    if cookie:
        headers["Cookie"] = cookie

    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return _clean_text(resp.text)


@retry(
    retry=retry_if_exception_type((requests.RequestException, RuntimeError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    reraise=True,
)
def _search_wechat_articles(wechat_id: str, count: int = 10) -> list[dict]:
    """Search WeChat articles via Sogou search engine."""
    params = {
        "type": "2",
        "query": wechat_id,
        "ie": "utf8",
        "page": "1",
    }
    resp = requests.get(_SOGOU_API, params=params, headers=_HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    articles = []

    for item in soup.select(".news-box .news-list li")[:count]:
        title_el = item.select_one("h3 a")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        link = title_el.get("href", "")
        if not link.startswith("http"):
            link = "https://weixin.sogou.com" + link

        date_el = item.select_one(".s-p")
        date_str = date_el.get_text(strip=True) if date_el else ""
        try:
            published_at = datetime.strptime(date_str, "%Y年%m月%d日").replace(tzinfo=timezone.utc)
        except Exception:
            published_at = datetime.now(timezone.utc)

        articles.append({"title": title, "url": link, "published_at": published_at})

    return articles


class WechatCrawlResult:
    def __init__(self, articles: list[dict], error: Optional[str] = None):
        self.articles = articles
        self.error = error
        self.success = error is None


def crawl_wechat(wechat_id: str, count: int = 10) -> WechatCrawlResult:
    """Crawl WeChat public account articles with retry and error handling."""
    try:
        article_list = _search_wechat_articles(wechat_id, count)
    except Exception as e:
        logger.error("WeChat search failed for %s: %s", wechat_id, e)
        return WechatCrawlResult(articles=[], error=str(e))

    results = []
    for article_meta in article_list:
        url = article_meta["url"]
        try:
            content = _fetch_article(url)
        except Exception as e:
            logger.warning("Failed to fetch article %s: %s", url, e)
            continue

        if len(content) < 100:
            continue

        title = article_meta["title"]
        full_content = f"{title}\n\n{content}"

        results.append(
            {
                "content": full_content[:3000],
                "url": url,
                "author": wechat_id,
                "published_at": article_meta["published_at"],
                "content_hash": _sha256(full_content[:3000]),
            }
        )

    logger.info("Crawled %d articles for WeChat account %s", len(results), wechat_id)
    return WechatCrawlResult(articles=results)
