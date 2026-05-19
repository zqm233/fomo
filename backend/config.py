from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy.engine.url import URL

load_dotenv(Path(__file__).parent / ".env")


def _compose_database_url() -> str:
    """Build postgresql URL from DB_* env, or use legacy DATABASE_URL if set."""
    legacy = os.getenv("DATABASE_URL", "").strip()
    if legacy:
        return legacy
    host = os.getenv("DB_HOST", "localhost")
    port_raw = os.getenv("DB_PORT", "5432").strip()
    try:
        port = int(port_raw)
    except ValueError:
        port = 5432
    user = os.getenv("DB_USER", "postgres").strip() or "postgres"
    password = os.getenv("DB_PASSWORD", "").strip()
    database = os.getenv("DB_NAME", "fomo").strip() or "fomo"
    sslmode = os.getenv("DB_SSLMODE", "").strip()
    query: dict[str, str] = {}
    if sslmode:
        query["sslmode"] = sslmode
    url = URL.create(
        "postgresql",
        username=user,
        password=password if password else None,
        host=host,
        port=port,
        database=database,
        query=query,
    )
    return url.render_as_string(hide_password=False)

# local=bge（固定名在 config）；ark / openai 用 LLM_EMBED_MODEL（兼容 ARK_EMBEDDING_MODEL）
_LOCAL_EMBEDDING_MODEL = "BAAI/bge-m3"
_OPENAI_COMPAT_EMBEDDING_MODEL = "text-embedding-3-small"
_ARK_MULTIMODAL_EMBEDDING_MODEL = "doubao-embedding-vision-251215"

_Ark_MM_SUFFIX = "/embeddings/multimodal"


def _collapse_duplicate_ark_multimodal_path(url: str) -> str:
    """Normalize …/embeddings/multimodal/embeddings/multimodal → single suffix."""
    u = url.strip().rstrip("/")
    dup = _Ark_MM_SUFFIX + _Ark_MM_SUFFIX
    while dup in u:
        u = u.replace(dup, _Ark_MM_SUFFIX)
    return u


def _openapi_root_for_ark_sdk(url: str) -> str:
    """
    Reduce a user-configured URL to OpenAPI gateway root (.../api/v3) for Ark(base_url).
    Handles legacy …/embeddings/multimodal full paths and duplicate suffixes.
    """
    u = _collapse_duplicate_ark_multimodal_path(url.strip()).rstrip("/")
    suf = _Ark_MM_SUFFIX
    if u.endswith(suf):
        u = u[: -len(suf)].rstrip("/")
    return u


def _embedding_provider() -> str:
    raw = os.getenv("EMBEDDING_PROVIDER", "local").strip().lower()
    return raw if raw in ("openai", "local", "ark") else "local"


_DEFAULT_CHAT_BASE = "https://ark.cn-beijing.volces.com/api/v3"
_DEFAULT_CHAT_MODEL = "doubao-seed-2-0-mini-260428"

# Production Vercel app; merged into cors_origins even when CORS_ORIGINS env is set.
_VERCEL_FRONTEND_ORIGIN = (
    "https://fomo-delta-azure.vercel.app"
)


class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    embedding_device: str = os.getenv("EMBEDDING_DEVICE", "auto").strip().lower()
    ark_embedding_dimensions: int = int(os.getenv("ARK_EMBEDDING_DIMENSIONS", "1024"))

    @property
    def embedding_provider(self) -> str:
        """须在进程内读到最新 .env 时每一步都调用；不可用类体一次性绑定。"""
        return _embedding_provider()

    # --- Chat：LLM_CHAT_* 优先，其次兼容 OPENAI_BASE_URL / LLM_MODEL ---
    @property
    def openai_base_url(self) -> str:
        return (
            os.getenv("LLM_CHAT_BASE_URL", "").strip()
            or os.getenv("OPENAI_BASE_URL", "").strip()
            or _DEFAULT_CHAT_BASE
        )

    @property
    def llm_model(self) -> str:
        return (
            os.getenv("LLM_CHAT_MODEL", "").strip()
            or os.getenv("LLM_MODEL", "").strip()
            or _DEFAULT_CHAT_MODEL
        )

    # --- Embedding：独立 Base URL，缺省则用对话网关 ---
    @property
    def embeddings_base_url(self) -> str:
        e = os.getenv("LLM_EMBED_BASE_URL", "").strip()
        return e if e else self.openai_base_url

    @property
    def ark_embedding_model(self) -> str:
        """方舟多模态模型 ID；兼容 ARK_EMBEDDING_MODEL。"""
        return (
            os.getenv("LLM_EMBED_MODEL", "").strip()
            or os.getenv("ARK_EMBEDDING_MODEL") or ""
        ).strip() or _ARK_MULTIMODAL_EMBEDDING_MODEL

    @property
    def openai_compatible_embedding_model(self) -> str:
        return (
            os.getenv("LLM_EMBED_MODEL", "").strip()
            or _OPENAI_COMPAT_EMBEDDING_MODEL
        )

    # --- 持久化：由 DB_HOST / DB_USER / DB_PASSWORD / DB_NAME 等在代码中拼接；可选 DATABASE_URL 覆盖 ---
    @property
    def database_url(self) -> str:
        return _compose_database_url()

    # --- 通知（任一侧有配置即视为可发）---
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    wecom_webhook_url: str = os.getenv("WECOM_WEBHOOK_URL", "")

    # --- HTTP ---
    @property
    def cors_origins(self) -> list[str]:
        raw = os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        )
        origins = [o.strip() for o in raw.split(",") if o.strip()]
        if _VERCEL_FRONTEND_ORIGIN not in origins:
            origins.append(_VERCEL_FRONTEND_ORIGIN)
        return origins

    # --- RSS 表单预设：RSSHub「Twitter 用户」订阅前缀（无尾斜杠）---
    @property
    def rsshub_twitter_base(self) -> str:
        raw = os.getenv(
            "RSSHUB_TWITTER_BASE",
            "https://rsshub-chromium-bundled-v580.onrender.com/twitter/user",
        ).strip()
        return raw.rstrip("/")

    # --- 公众号 RSS（waytomaster）：Render IP 常被 CF 403，改由 Vercel 代拉 ---
    @property
    def rss_edge_fetch_url(self) -> str:
        raw = os.getenv("RSS_EDGE_FETCH_URL", "").strip()
        if raw:
            return raw.rstrip("/")
        return f"{_VERCEL_FRONTEND_ORIGIN.rstrip('/')}/api/internal/rss-fetch"

    # --- 定时任务（美东；数值由 scheduler 解释）---
    pre_market_hour: int = int(os.getenv("PRE_MARKET_HOUR", "8"))
    pre_market_minute: int = int(os.getenv("PRE_MARKET_MINUTE", "30"))
    post_market_hour: int = int(os.getenv("POST_MARKET_HOUR", "16"))
    post_market_minute: int = int(os.getenv("POST_MARKET_MINUTE", "30"))

    # --- 热门股池窗口：最近 N 个「美股交易日」(NYSE)；简讯保留仍用下方自然日 timedelta ---
    hot_pool_window_days: int = int(os.getenv("HOT_POOL_WINDOW_DAYS", "7"))
    hot_pool_max_size: int = int(os.getenv("HOT_POOL_MAX_SIZE", "15"))

    # 临时维护：POST /api/pipeline/research/reembed-vectors 须在 Header X-Reembed-Secret 中携带与本值一致的密钥
    research_reembed_secret: str = os.getenv("RESEARCH_REEMBED_SECRET", "").strip()

    @property
    def embedding_model(self) -> str:
        if self.embedding_provider == "local":
            return _LOCAL_EMBEDDING_MODEL
        if self.embedding_provider == "ark":
            return self.ark_embedding_model
        return self.openai_compatible_embedding_model

    @property
    def ark_sdk_base_url(self) -> str | None:
        """
        Optional ``Ark(base_url=...)`` override (OpenAPI gateway root, e.g. …/api/v3).
        If unset, the official SDK uses its built-in Beijing endpoint — no Embedding URL env required.

        Compatible with legacy ``ARK_EMBEDDINGS_URL`` when it pointed at the multimodal path.
        Prefer ``ARK_API_BASE_URL`` for new configs.
        """
        pref = os.getenv("ARK_API_BASE_URL", "").strip()
        if pref:
            return _openapi_root_for_ark_sdk(pref)
        legacy = os.getenv("ARK_EMBEDDINGS_URL", "").strip()
        if legacy:
            return _openapi_root_for_ark_sdk(legacy)
        return None

    @property
    def ark_embedding_api_key(self) -> str:
        """与 LLM 同源：优先专用 ARK_API_KEY，否则使用 OPENAI_API_KEY。"""
        return (os.getenv("ARK_API_KEY", "").strip() or self.openai_api_key).strip()

    @property
    def llm_kwargs(self) -> dict[str, Any]:
        out: dict[str, Any] = {"model": self.llm_model, "api_key": self.openai_api_key}
        if self.openai_base_url:
            out["base_url"] = self.openai_base_url
        return out

    @property
    def lite_llm_kwargs(self) -> dict[str, Any]:
        """可选轻量推理；不配 LLM_LITE_MODEL 时与普通对话完全一致。"""
        lite_model = os.getenv("LLM_LITE_MODEL", "").strip()
        if not lite_model:
            return self.llm_kwargs
        base = (
            os.getenv("LLM_LITE_BASE_URL", "").strip() or self.openai_base_url
        )
        out: dict[str, Any] = {
            "model": lite_model,
            "api_key": self.openai_api_key,
        }
        if base:
            out["base_url"] = base
        return out

    @property
    def notifications_enabled(self) -> bool:
        return bool(self.telegram_bot_token or self.wecom_webhook_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
