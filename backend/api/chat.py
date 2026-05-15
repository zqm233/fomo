from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import ChatHistory
from agents.chat_agent import stream_chat_response

router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    source_ids: List[str] = []


class MessageOut(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    created_at: str


@router.post("/stream")
async def chat_stream(body: ChatRequest, db: Session = Depends(get_db)):
    """SSE streaming chat endpoint."""
    session_id = body.session_id or str(uuid.uuid4())

    history = (
        db.query(ChatHistory)
        .filter(ChatHistory.session_id == session_id)
        .order_by(ChatHistory.created_at.asc())
        .limit(20)
        .all()
    )
    history_dicts = [{"role": h.role, "content": h.content} for h in history]

    user_msg = ChatHistory(
        session_id=session_id,
        role="user",
        content=body.question,
        source_ids=json.dumps(body.source_ids),
    )
    db.add(user_msg)
    db.commit()

    async def event_generator():
        full_response = ""
        yield f"data: {json.dumps({'type': 'session_id', 'session_id': session_id})}\n\n"

        async for token in stream_chat_response(
            question=body.question,
            history=history_dicts,
            source_ids=body.source_ids,
        ):
            full_response += token
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        ai_msg = ChatHistory(
            session_id=session_id,
            role="assistant",
            content=full_response,
            source_ids=json.dumps(body.source_ids),
        )
        new_db = db.__class__(bind=db.get_bind())
        new_db.add(ai_msg)
        new_db.commit()
        new_db.close()

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history/{session_id}", response_model=List[MessageOut])
def get_history(session_id: str, db: Session = Depends(get_db)):
    messages = (
        db.query(ChatHistory)
        .filter(ChatHistory.session_id == session_id)
        .order_by(ChatHistory.created_at.asc())
        .all()
    )
    return [
        MessageOut(
            id=m.id,
            session_id=m.session_id,
            role=m.role,
            content=m.content,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]


@router.delete("/history/{session_id}", status_code=204)
def clear_history(session_id: str, db: Session = Depends(get_db)):
    db.query(ChatHistory).filter(ChatHistory.session_id == session_id).delete()
    db.commit()
