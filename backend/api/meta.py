"""Non-secret values for SPA forms (URLs, presets)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from config import get_settings

router = APIRouter()


class ClientMetaOut(BaseModel):
    """Public client hints — no secrets."""

    rsshub_twitter_base: str


@router.get("/client-config", response_model=ClientMetaOut)
def client_config():
    settings = get_settings()
    base = settings.rsshub_twitter_base.rstrip("/")
    return ClientMetaOut(rsshub_twitter_base=base)
