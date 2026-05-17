from __future__ import annotations

import logging
from typing import AsyncGenerator, List

from langchain.schema import AIMessage, HumanMessage, SystemMessage

from agents.base import get_llm, get_active_prompt
from tools.rag_tool import rag_search

logger = logging.getLogger(__name__)


def build_context(source_ids: List[str], question: str, n_results: int = 6) -> str:
    docs = rag_search(query=question, source_ids=source_ids, n_results=n_results)
    if not docs:
        return ""
    blocks = []
    for i, d in enumerate(docs, 1):
        meta = d.get("metadata", {})
        author = meta.get("author", "未知来源")
        date = meta.get("published_date", "")
        blocks.append(f"[参考{i}] {author} {date}\n{d['content']}")
    return "\n\n".join(blocks)


async def stream_chat_response(
    question: str,
    history: List[dict],
    source_ids: List[str],
) -> AsyncGenerator[str, None]:
    """
    Stream chat response tokens for the RAG Q&A agent.
    Yields text chunks as they arrive from the LLM.
    """
    system_prompt = get_active_prompt("chat_agent") or "你是一位专业的美股投研助手。"

    context = build_context(source_ids, question)
    logger.info("RAG context (%d chars):\n%s", len(context), context[:500] if context else "(empty)")
    if context:
        system_with_context = (
            f"{system_prompt}\n\n"
            f"以下是知识库中的相关内容，请基于这些内容回答：\n\n{context}"
        )
    else:
        system_with_context = (
            f"{system_prompt}\n\n（知识库中未找到与此问题相关的内容，请如实说明。）"
        )

    messages = [SystemMessage(content=system_with_context)]
    for msg in history[-10:]:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=question))

    llm = get_llm(temperature=0.4)

    async for chunk in llm.astream(messages):
        token = chunk.content
        if token:
            yield token
