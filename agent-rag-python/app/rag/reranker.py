"""Rerank 层：SiliconFlow Qwen3-Reranker API（cross-encoder）。

任何环节失败都返回 None，由调用方降级为 RRF 分数排序（见 02 文档 6.3）。
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class SiliconFlowReranker:
    """SiliconFlow Qwen3-Reranker API 封装。分数已在 [0, 1] 区间，按相关性降序。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._settings.siliconflow_api_key}",
            "Content-Type": "application/json",
        }

    @property
    def _rerank_url(self) -> str:
        return f"{self._settings.siliconflow_base_url}/rerank"

    def rerank(self, query: str, contents: list[str]) -> list[float] | None:
        """返回与 contents 等长的分数列表（按 contents 原始顺序）；不可用时返回 None。"""
        if not self._settings.reranker_enabled or not contents:
            return None

        logger.debug("rerank: query='%s...' docs=%d top_n=%d", query[:60], len(contents),
                     self._settings.reranker_top_n)
        try:
            resp = httpx.post(
                self._rerank_url,
                headers=self._headers,
                json={
                    "model": self._settings.reranker_model_name,
                    "query": query,
                    "documents": contents,
                    "top_n": self._settings.reranker_top_n,
                    "return_documents": False,
                },
                timeout=30,
            )
            resp.raise_for_status()
            results = resp.json()["results"]
            logger.debug("rerank OK: %d results, top score=%.4f", len(results),
                         results[0]["relevance_score"] if results else 0.0)
        except Exception as exc:  # noqa: BLE001
            logger.warning("rerank API failed, degrade to rrf order: %s", exc)
            return None

        # 按 contents 原始索引重建分数列表
        scores = [0.0] * len(contents)
        for r in results:
            idx = r["index"]
            if idx < len(scores):
                scores[idx] = float(r["relevance_score"])
        return scores

    def health(self) -> str:
        if not self._settings.reranker_enabled:
            return "disabled"
        try:
            scores = self.rerank("健康检查", ["这是一个健康检查测试段落。"])
            return "ok" if scores else "error"
        except Exception as exc:  # noqa: BLE001
            return f"error: {exc}"


def build_reranker(settings: Settings) -> SiliconFlowReranker:
    return SiliconFlowReranker(settings)
