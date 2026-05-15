from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).digest().hex()


class TwitterCrawlResult:
    def __init__(self, tweets: list[dict], error: Optional[str] = None):
        self.tweets = tweets
        self.error = error
        self.success = error is None


@retry(
    retry=retry_if_exception_type(RuntimeError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _fetch_tweets_with_retry(handle: str, count: int) -> list[dict]:
    """Call x-tweet-fetcher subprocess and return parsed tweet list."""
    fetcher_path = Path(settings.twitter_fetcher_path)
    if not fetcher_path.exists():
        raise FileNotFoundError(f"x-tweet-fetcher not found at {fetcher_path}")

    cmd = [
        sys.executable,
        str(fetcher_path / "main.py"),
        "--user", handle.lstrip("@"),
        "--count", str(count),
        "--format", "json",
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(fetcher_path),
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Twitter fetcher timed out for @{handle}") from e

    if result.returncode != 0:
        raise RuntimeError(
            f"Twitter fetcher failed for @{handle}: {result.stderr[:500]}"
        )

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse fetcher output for @{handle}") from e


def crawl_twitter(handle: str, count: int = 50) -> TwitterCrawlResult:
    """Crawl tweets for a given Twitter handle with retry and error handling."""
    if not settings.twitter_fetcher_path:
        logger.warning("TWITTER_FETCHER_PATH not configured; skipping Twitter crawl")
        return TwitterCrawlResult(tweets=[], error="TWITTER_FETCHER_PATH not configured")

    try:
        raw_tweets = _fetch_tweets_with_retry(handle, count)
    except Exception as e:
        logger.error("Twitter crawl failed for @%s after retries: %s", handle, e)
        return TwitterCrawlResult(tweets=[], error=str(e))

    tweets = []
    for t in raw_tweets:
        text = t.get("text") or t.get("full_text") or ""
        if not text.strip():
            continue
        url = t.get("url") or t.get("tweet_url") or ""
        created = t.get("created_at") or t.get("date") or ""
        try:
            published_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except Exception:
            published_at = datetime.now(timezone.utc)

        tweets.append(
            {
                "content": text.strip(),
                "url": url,
                "author": handle,
                "published_at": published_at,
                "content_hash": _sha256(text.strip()),
            }
        )

    logger.info("Crawled %d tweets for @%s", len(tweets), handle)
    return TwitterCrawlResult(tweets=tweets)
