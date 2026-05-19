from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from db.database import init_db
from scheduler.tasks import start_scheduler, shutdown_scheduler
from api import sources, meta, reports, chat, pipeline, prompts, articles, tickers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


def log_model_config() -> None:
    """Log resolved model IDs once at startup (English; avoids duplicating scheduler lines)."""
    s = get_settings()
    ck = s.llm_kwargs
    lk = s.lite_llm_kwargs
    logger.info("LLM chat model: %s", ck.get("model"))
    logger.info("LLM lite model: %s", lk.get("model"))
    logger.info("Embedding model: %s", s.embedding_model)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting FOMO backend…")
    init_db()
    logger.info("Database layer ready — starting scheduler…")
    start_scheduler()
    log_model_config()
    logger.info("Startup complete.")
    yield
    logger.info("Shutting down FOMO backend…")
    shutdown_scheduler()


app = FastAPI(
    title="FOMO 美股 AI 投研系统",
    description="美股财经投研 AI Agent 后端 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meta.router, prefix="/api/meta", tags=["Meta"])
app.include_router(sources.router, prefix="/api/sources", tags=["数据源"])
app.include_router(reports.router, prefix="/api/reports", tags=["简报"])
app.include_router(chat.router, prefix="/api/chat", tags=["RAG 对话"])
app.include_router(pipeline.router, prefix="/api/pipeline", tags=["流水线"])
app.include_router(prompts.router, prefix="/api/prompts", tags=["Prompt 管理"])
app.include_router(articles.router, prefix="/api/articles", tags=["文章库"])
app.include_router(tickers.router, prefix="/api/tickers/hot", tags=["热门股池"])


@app.get("/api/health", tags=["系统"])
async def health() -> dict:
    return {"status": "ok", "version": "1.0.0"}
