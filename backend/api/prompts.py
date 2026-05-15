from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Prompt

router = APIRouter()

AGENT_NAMES = ("sentiment_agent", "hotspot_agent", "summary_agent", "chat_agent")


class PromptOut(BaseModel):
    id: str
    agent_name: str
    prompt_text: str
    version: int
    is_active: bool
    updated_at: str
    created_at: str


class PromptUpdate(BaseModel):
    prompt_text: str


def _to_out(p: Prompt) -> PromptOut:
    return PromptOut(
        id=p.id,
        agent_name=p.agent_name,
        prompt_text=p.prompt_text,
        version=p.version,
        is_active=p.is_active,
        updated_at=p.updated_at.isoformat(),
        created_at=p.created_at.isoformat(),
    )


@router.get("", response_model=List[PromptOut])
def list_prompts(db: Session = Depends(get_db)):
    """List all active prompts, one per agent."""
    prompts = []
    for agent_name in AGENT_NAMES:
        prompt = (
            db.query(Prompt)
            .filter(Prompt.agent_name == agent_name, Prompt.is_active == True)
            .order_by(Prompt.version.desc())
            .first()
        )
        if prompt:
            prompts.append(_to_out(prompt))
    return prompts


@router.get("/{agent_name}", response_model=PromptOut)
def get_prompt(agent_name: str, db: Session = Depends(get_db)):
    if agent_name not in AGENT_NAMES:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {agent_name}")
    prompt = (
        db.query(Prompt)
        .filter(Prompt.agent_name == agent_name, Prompt.is_active == True)
        .order_by(Prompt.version.desc())
        .first()
    )
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return _to_out(prompt)


@router.put("/{agent_name}", response_model=PromptOut)
def update_prompt(agent_name: str, body: PromptUpdate, db: Session = Depends(get_db)):
    """Save a new version of the prompt and mark it active."""
    if agent_name not in AGENT_NAMES:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {agent_name}")

    current = (
        db.query(Prompt)
        .filter(Prompt.agent_name == agent_name, Prompt.is_active == True)
        .order_by(Prompt.version.desc())
        .first()
    )

    new_version = (current.version + 1) if current else 1

    if current:
        current.is_active = False
        db.flush()

    new_prompt = Prompt(
        agent_name=agent_name,
        prompt_text=body.prompt_text,
        version=new_version,
        is_active=True,
    )
    db.add(new_prompt)
    db.commit()
    db.refresh(new_prompt)
    return _to_out(new_prompt)


@router.get("/{agent_name}/history", response_model=List[PromptOut])
def get_prompt_history(agent_name: str, db: Session = Depends(get_db)):
    if agent_name not in AGENT_NAMES:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {agent_name}")
    prompts = (
        db.query(Prompt)
        .filter(Prompt.agent_name == agent_name)
        .order_by(Prompt.version.desc())
        .limit(10)
        .all()
    )
    return [_to_out(p) for p in prompts]


@router.post("/{agent_name}/rollback/{version}", response_model=PromptOut)
def rollback_prompt(agent_name: str, version: int, db: Session = Depends(get_db)):
    """Activate a historical version of the prompt."""
    target = (
        db.query(Prompt)
        .filter(Prompt.agent_name == agent_name, Prompt.version == version)
        .first()
    )
    if not target:
        raise HTTPException(status_code=404, detail="Prompt version not found")

    db.query(Prompt).filter(
        Prompt.agent_name == agent_name, Prompt.is_active == True
    ).update({"is_active": False})

    target.is_active = True
    db.commit()
    db.refresh(target)
    return _to_out(target)
