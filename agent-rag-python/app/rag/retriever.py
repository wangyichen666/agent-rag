"""混合检索：稠密 + 稀疏双路召回，RRF 融合，可选 Rerank 精排。"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from app.core.config import Settings
from app.rag.reranker import BgeReranker
from app.rag.vector_store import ScoredChunk, VectorStore

logger = logging.getLogger(__name__)


@dataclass
class Candidate:
    chunk_id: str
    doc_id: str
    content: str
    metadata: dict
    dense_rank: int | None = None
    sparse_rank: int | None = None
    rrf_score: float = 0.0
    rerank_score: float | None = None


@dataclass
class RankResult:
    selected: list[Candidate]
    rerank_degraded: bool          # True 表示 rerank 不可用、按 RRF 排序
    rerank_scores: list[float] = field(default_factory=list)


def rrf_fuse(dense_hits: list[ScoredChunk], sparse_hits: list[ScoredChunk],
             rrf_k: int = 60) -> list[Candidate]:
    """Reciprocal Rank Fusion：score = Σ 1/(k + rank)。"""
    pool: dict[str, Candidate] = {}

    def visit(hits: list[ScoredChunk], channel: str) -> None:
        for h in hits:
            c = pool.get(h.chunk_id)
            if c is None:
                c = Candidate(h.chunk_id, h.doc_id, h.content, h.metadata)
                pool[h.chunk_id] = c
            if channel == "dense":
                c.dense_rank = h.rank
            else:
                c.sparse_rank = h.rank
            c.rrf_score += 1.0 / (rrf_k + h.rank)

    visit(dense_hits, "dense")
    visit(sparse_hits, "sparse")
    return sorted(pool.values(), key=lambda c: c.rrf_score, reverse=True)


async def hybrid_retrieve(store: VectorStore, embedder, kb_ids: list[str], query: str,
                          settings: Settings, dense_top_k: int, sparse_top_k: int) -> list[Candidate]:
    """双路并发召回 + RRF 融合。稀疏路失败时降级为纯稠密。"""
    embedded = await asyncio.to_thread(embedder.embed_texts, [query], True)
    dense_vec, sparse_vec = embedded.dense[0], embedded.sparse[0]

    dense_task = asyncio.to_thread(store.search_dense, kb_ids, dense_vec, dense_top_k)
    sparse_task = asyncio.to_thread(store.search_sparse, kb_ids, sparse_vec, sparse_top_k)
    dense_hits: list[ScoredChunk] = []
    sparse_hits: list[ScoredChunk] = []
    results = await asyncio.gather(dense_task, sparse_task, return_exceptions=True)
    if isinstance(results[0], Exception):
        logger.error("dense search failed: %s", results[0])
        raise results[0]
    dense_hits = results[0]
    if isinstance(results[1], Exception):
        logger.warning("sparse search failed, degrade to dense-only: %s", results[1])
    else:
        sparse_hits = results[1]

    return rrf_fuse(dense_hits, sparse_hits, settings.rrf_k)


async def rank_candidates(query: str, candidates: list[Candidate], reranker: BgeReranker,
                          top_n: int) -> RankResult:
    """Rerank 精排；失败时按 RRF 顺序截断（降级）。"""
    if not candidates:
        return RankResult([], rerank_degraded=False, rerank_scores=[])
    pool = candidates[: max(top_n * 4, top_n)]
    scores = await asyncio.to_thread(reranker.rerank, query, [c.content for c in pool])
    if scores is None:
        logger.info("rerank unavailable, use rrf order")
        return RankResult(pool[:top_n], rerank_degraded=True,
                          rerank_scores=[c.rrf_score for c in pool[:top_n]])
    for c, s in zip(pool, scores):
        c.rerank_score = s
    ordered = sorted(pool, key=lambda c: c.rerank_score or 0.0, reverse=True)
    selected = ordered[:top_n]
    return RankResult(selected, rerank_degraded=False,
                      rerank_scores=[c.rerank_score or 0.0 for c in selected])
