from __future__ import annotations

import logging
from typing import Optional

from langchain_openai import ChatOpenAI

from config import get_settings
from db.database import SessionLocal
from db.models import Prompt

logger = logging.getLogger(__name__)
settings = get_settings()


def get_llm(temperature: float = 0.3) -> ChatOpenAI:
    return ChatOpenAI(temperature=temperature, **settings.llm_kwargs)


def get_active_prompt(agent_name: str) -> Optional[str]:
    """Load the active prompt for an agent from the database."""
    db = SessionLocal()
    try:
        prompt = (
            db.query(Prompt)
            .filter(Prompt.agent_name == agent_name, Prompt.is_active == True)
            .order_by(Prompt.version.desc())
            .first()
        )
        if prompt:
            return prompt.prompt_text
        logger.warning("No active prompt found for agent: %s", agent_name)
        return None
    finally:
        db.close()
