"""
火山方舟多模态 Embedding：官方 SDK（volcenginesdkarkruntime），与文档一致调用
``client.multimodal_embeddings.create``。

默认网关与会话路径由 SDK 固定（通常为 ``https://ark.cn-beijing.volces.com/api/v3``
+ ``/embeddings/multimodal``），**不必**再配置 Embedding 专用完整 URL。
RAG 仅对文本切块请求： ``input=[{"type": "text", "text": ...}]`` 。

可选：环境变量 ``ARK_API_BASE_URL``（或兼容旧字段 ``ARK_EMBEDDINGS_URL``）仅用于**覆盖网关根路径**，
由 ``config.Settings.ark_sdk_base_url`` 归一处理后传入 ``Ark(base_url=...)``。
"""

from __future__ import annotations

import logging

from langchain_core.embeddings import Embeddings
from volcenginesdkarkruntime import Ark

logger = logging.getLogger(__name__)


class ArkMultimodalEmbeddings(Embeddings):
    """LangChain Embeddings backed by Ark multimodal API (SDK), text chunks only."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimensions: int = 1024,
        base_url: str | None = None,
        timeout: float = 600.0,
    ) -> None:
        if not api_key:
            raise ValueError(
                "Ark embedding api_key is empty (set ARK_API_KEY or OPENAI_API_KEY)"
            )
        self._model = model.strip()
        self._dimensions = dimensions

        ark_kw: dict = {"api_key": api_key, "timeout": timeout}
        if base_url:
            ark_kw["base_url"] = base_url.strip()
        self._client = Ark(**ark_kw)

    def close(self) -> None:
        closer = getattr(self._client, "close", None)
        if callable(closer):
            closer()

    def _embed_one(self, text: str) -> list[float]:
        resp = self._client.multimodal_embeddings.create(
            model=self._model,
            input=[{"type": "text", "text": text}],
            dimensions=self._dimensions,
        )
        vec = resp.data.embedding
        if len(vec) != self._dimensions:
            logger.warning(
                "Embedding length %s != requested dimensions %s; "
                "check ARK_EMBEDDING_DIMENSIONS / pgvector column",
                len(vec),
                self._dimensions,
            )
        return [float(x) for x in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # 服务端按 input 聚合为单向量；多块文本逐条请求
        return [self._embed_one(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)
