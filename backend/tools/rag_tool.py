from __future__ import annotations

import logging
from typing import List, Optional

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from vector_store.chroma_store import query_documents

logger = logging.getLogger(__name__)


class RAGInput(BaseModel):
    query: str = Field(description="检索查询文本")
    source_ids: List[str] = Field(description="要检索的数据源 ID 列表；空列表表示检索所有")
    n_results: int = Field(default=5, description="最多返回的文档数量")
    date_filter: Optional[str] = Field(default=None, description="可选：只检索指定日期（YYYY-MM-DD）的内容")


class RAGTool(BaseTool):
    """全局 RAG 检索工具 - 所有 Agent 统一调用"""

    name: str = "rag_retrieval"
    description: str = (
        "从向量知识库检索相关的推文和公众号文章内容。"
        "输入检索查询和数据源 ID 列表，返回最相关的文档片段。"
    )
    args_schema: type[BaseModel] = RAGInput

    def _run(
        self,
        query: str,
        source_ids: List[str],
        n_results: int = 5,
        date_filter: Optional[str] = None,
    ) -> str:
        where = None
        if date_filter:
            where = {"published_date": {"$eq": date_filter}}

        results = query_documents(
            source_ids=source_ids,
            query_text=query,
            n_results=n_results,
            where=where,
        )

        if not results:
            return "未找到相关内容。"

        formatted = []
        for i, r in enumerate(results, 1):
            meta = r.get("metadata", {})
            source = meta.get("author", meta.get("source_id", "未知"))
            date = meta.get("published_date", "")
            score = r.get("score", 0)
            content = r["content"][:500]
            formatted.append(
                f"[{i}] 来源: {source}  日期: {date}  相关度: {score:.2f}\n{content}"
            )

        return "\n\n---\n\n".join(formatted)

    async def _arun(self, *args, **kwargs) -> str:
        return self._run(*args, **kwargs)


def get_rag_tool() -> RAGTool:
    return RAGTool()


def rag_search(
    query: str,
    source_ids: List[str],
    n_results: int = 5,
    date_filter: Optional[str] = None,
) -> List[dict]:
    """Convenience function for direct use in pipeline (not via LangChain tool call)."""
    where = None
    if date_filter:
        where = {"published_date": {"$eq": date_filter}}
    return query_documents(
        source_ids=source_ids,
        query_text=query,
        n_results=n_results,
        where=where,
    )
