"""混合检索：稠密 + 稀疏双路召回，RRF 融合，可选 Rerank 精排。

SiliconFlow Qwen3-Embedding 不返回稀疏向量，此时自动降级为纯稠密检索。
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.core.config import Settings
from app.rag.reranker import SiliconFlowReranker
from app.rag.vector_store import ScoredChunk, VectorStore

if TYPE_CHECKING:  # 避免 retriever -> graph_retriever -> extractor -> generator -> retriever 循环
    from app.rag.graph_retriever import GraphCandidate

logger = logging.getLogger(__name__)


@dataclass
class Candidate:
    chunk_id: str
    doc_id: str
    content: str
    metadata: dict
    dense_rank: int | None = None
    sparse_rank: int | None = None
    graph_rank: int | None = None
    graph_hops: int = 0
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


def fuse_graph(candidates: list[Candidate], graph_cands: list[GraphCandidate],
               rrf_k: int = 60) -> list[Candidate]:
    """把图通道候选并入已有 RRF 池：graph_rank 作为独立通道参与融合。"""
    if not graph_cands:
        return candidates
    pool = {c.chunk_id: c for c in candidates}
    for i, g in enumerate(graph_cands, start=1):
        c = pool.get(g.chunk_id)
        if c is None:
            c = Candidate(g.chunk_id, g.doc_id, g.content, g.metadata)
            pool[g.chunk_id] = c
        c.graph_rank = i
        c.graph_hops = g.hop if not c.graph_hops else min(c.graph_hops, g.hop)
        c.rrf_score += 1.0 / (rrf_k + i)
    return sorted(pool.values(), key=lambda c: c.rrf_score, reverse=True)


def _has_sparse(sparse_vec: dict[int, float]) -> bool:
    """判断稀疏向量是否有效（非空且有非零权重）。"""
    return bool(sparse_vec) and any(v != 0.0 for v in sparse_vec.values())


async def hybrid_retrieve(store: VectorStore, embedder, kb_ids: list[str], query: str,
                          settings: Settings, dense_top_k: int, sparse_top_k: int) -> list[Candidate]:
    """双路并发召回 + RRF 融合。稀疏向量为空时自动降级为纯稠密。"""
    embedded = await asyncio.to_thread(embedder.embed_texts, [query], True)
    dense_vec, sparse_vec = embedded.dense[0], embedded.sparse[0]

    if not _has_sparse(sparse_vec):
        # SiliconFlow Qwen3-Embedding 无稀疏向量，仅走稠密路
        logger.debug("sparse vector empty, dense-only retrieval")
        dense_hits = await asyncio.to_thread(store.search_dense, kb_ids, dense_vec, dense_top_k)
        return rrf_fuse(dense_hits, [], settings.rrf_k)

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


async def rank_candidates(query: str, candidates: list[Candidate], reranker: SiliconFlowReranker,
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
