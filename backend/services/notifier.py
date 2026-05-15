from __future__ import annotations

import logging

import httpx
import requests

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _send_telegram(message: str) -> bool:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return False
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        logger.info("Telegram notification sent")
        return True
    except Exception as e:
        logger.error("Failed to send Telegram notification: %s", e)
        return False


def _send_wecom(message: str) -> bool:
    if not settings.wecom_webhook_url:
        return False
    payload = {"msgtype": "markdown", "markdown": {"content": message}}
    try:
        resp = requests.post(settings.wecom_webhook_url, json=payload, timeout=15)
        resp.raise_for_status()
        logger.info("WeCom notification sent")
        return True
    except Exception as e:
        logger.error("Failed to send WeCom notification: %s", e)
        return False


def notify_report_ready(
    report_date: str,
    report_type: str,
    sentiment_label: str,
    hotspot_count: int,
    summary_preview: str,
) -> None:
    """Send notification when a report is ready. No-op if no channels configured."""
    if not settings.notifications_enabled:
        return

    type_label = "盘前简讯" if report_type == "pre" else "盘后复盘"
    preview = summary_preview[:200].replace("\n", " ")

    message = (
        f"📊 *FOMO {type_label}已生成* — {report_date}\n\n"
        f"市场情绪：{sentiment_label}\n"
        f"热点主题：{hotspot_count} 个\n\n"
        f"{preview}…\n\n"
        f"_打开 FOMO 查看完整简报_"
    )

    _send_telegram(message)
    _send_wecom(message)
