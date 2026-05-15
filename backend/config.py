from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


class Settings:
    # LLM
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    # Storage
    chroma_persist_dir: str = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")
    sqlite_path: str = os.getenv("SQLITE_PATH", "./data/fomo.db")

    # Crawlers
    twitter_fetcher_path: str = os.getenv("TWITTER_FETCHER_PATH", "")
    wechat_cookie: str = os.getenv("WECHAT_COOKIE", "")

    # Notifications
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    wecom_webhook_url: str = os.getenv("WECOM_WEBHOOK_URL", "")

    # CORS
    cors_origins: List[str] = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if o.strip()
    ]

    # Scheduler times (America/New_York)
    pre_market_hour: int = int(os.getenv("PRE_MARKET_HOUR", "8"))
    pre_market_minute: int = int(os.getenv("PRE_MARKET_MINUTE", "30"))
    post_market_hour: int = int(os.getenv("POST_MARKET_HOUR", "16"))
    post_market_minute: int = int(os.getenv("POST_MARKET_MINUTE", "30"))

    @property
    def llm_kwargs(self) -> dict:
        kwargs: dict = {"model": self.llm_model, "api_key": self.openai_api_key}
        if self.openai_base_url:
            kwargs["base_url"] = self.openai_base_url
        return kwargs

    @property
    def sqlite_url(self) -> str:
        path = Path(self.sqlite_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.resolve()}"

    @property
    def notifications_enabled(self) -> bool:
        return bool(self.telegram_bot_token or self.wecom_webhook_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
