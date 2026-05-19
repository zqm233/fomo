"""后端启动时在后台 ping RSSHub（Render 休眠），正式拉 RSS 前提前唤醒。"""

from __future__ import annotations

import logging
import threading
import time
from urllib.parse import urlparse

import requests

from config import get_settings

logger = logging.getLogger(__name__)

_WAKE_UA = "Mozilla/5.0 (compatible; FOMO/1.0)"
_PING_TIMEOUT = (10, 120)
_FOLLOWUP_SEC = 45


def _rsshub_origin() -> str | None:
    base = get_settings().rsshub_twitter_base.strip()
    if not base:
        return None
    p = urlparse(base)
    if p.scheme not in ("http", "https") or not p.netloc:
        return None
    return f"{p.scheme}://{p.netloc}"


def ping_rsshub() -> None:
    origin = _rsshub_origin()
    if not origin:
        return
    url = f"{origin}/"
    try:
        r = requests.get(
            url,
            headers={"User-Agent": _WAKE_UA, "Accept": "text/html, */*"},
            timeout=_PING_TIMEOUT,
            allow_redirects=True,
        )
        logger.info(
            "RSSHub wake ping %s → HTTP %s (%s bytes)",
            url,
            r.status_code,
            len(r.content or b""),
        )
    except requests.RequestException as e:
        logger.info("RSSHub wake ping %s (triggered: %s)", url, e)


def schedule_rsshub_wake_on_startup() -> None:
    origin = _rsshub_origin()
    if not origin:
        return

    def _run() -> None:
        ping_rsshub()
        time.sleep(_FOLLOWUP_SEC)
        ping_rsshub()

    threading.Thread(target=_run, name="rsshub-wake", daemon=True).start()
    logger.info("RSSHub wake scheduled in background (origin=%s)", origin)
