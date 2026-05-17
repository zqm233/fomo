from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# 向量模型名仅在代码里维护（env 不再提供 EMBEDDING_MODEL）
_LOCAL_EMBEDDING_MODEL = "BAAI/bge-m3"
_OPENAI_COMPAT_EMBEDDING_MODEL = "text-embedding-3-small"


def _embedding_provider() -> str:
    raw = os.getenv("EMBEDDING_PROVIDER", "local").strip().lower()
    return raw if raw in ("openai", "local") else "local"


class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv(
        "OPENAI_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"
    )
    llm_model: str = os.getenv("LLM_MODEL", "doubao-seed-2-0-mini-260428")

    # --- 向量：local=本机 HuggingFace；openai=云端 OpenAI 兼容 embedding ---
    embedding_provider: str = _embedding_provider()
    embedding_device: str = os.getenv("EMBEDDING_DEVICE", "auto").strip().lower()

    # --- 持久化 ---
    chroma_persist_dir: str = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")
    sqlite_path: str = os.getenv("SQLITE_PATH", "./data/fomo.db")

    # --- 通知（任一侧有配置即视为可发）---
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    wecom_webhook_url: str = os.getenv("WECOM_WEBHOOK_URL", "")

    # --- HTTP ---
    cors_origins: list[str] = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if o.strip()
    ]

    # --- 定时任务（美东；数值由 scheduler 解释）---
    pre_market_hour: int = int(os.getenv("PRE_MARKET_HOUR", "8"))
    pre_market_minute: int = int(os.getenv("PRE_MARKET_MINUTE", "30"))
    post_market_hour: int = int(os.getenv("POST_MARKET_HOUR", "16"))
    post_market_minute: int = int(os.getenv("POST_MARKET_MINUTE", "30"))

    # --- 热门股池窗口：最近 N 个「美股交易日」(NYSE)；简讯保留仍用下方自然日 timedelta ---
    hot_pool_window_days: int = int(os.getenv("HOT_POOL_WINDOW_DAYS", "7"))
    hot_pool_max_size: int = int(os.getenv("HOT_POOL_MAX_SIZE", "15"))
    @property
    def embedding_model(self) -> str:
        if self.embedding_provider == "local":
            return _LOCAL_EMBEDDING_MODEL
        return _OPENAI_COMPAT_EMBEDDING_MODEL

    @property
    def llm_kwargs(self) -> dict[str, Any]:
        out: dict[str, Any] = {"model": self.llm_model, "api_key": self.openai_api_key}
        if self.openai_base_url:
            out["base_url"] = self.openai_base_url
        return out

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
