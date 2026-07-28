"""RAG 全链路调试路由：可追溯 query → retrieve → rerank 全流程。"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import AppDeps, get_deps
from app.core.security import verify_internal_token
from app.rag.generator import SYSTEM_PROMPT, _format_context_block, build_citations, trim_contexts
from app.rag.retriever import Candidate, hybrid_retrieve, rank_candidates

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_internal_token)])


# ---------- 请求 / 响应模型 ----------

class DebugTraceRequest(BaseModel):
    kb_ids: list[str]
    query: str
    dense_top_k: int = 20
    sparse_top_k: int = 20
    rerank_top_n: int = 10
    score_threshold: float = 0.0  # debug 模式默认不过滤


class CandidateItem(BaseModel):
    """一条候选块的可读信息。"""
    chunk_id: str
    doc_id: str
    source_file: str = ""
    title_path: list[str] = Field(default_factory=list)
    page: int | None = None
    content: str
    dense_rank: int | None = None
    dense_score: float | None = None
    sparse_rank: int | None = None
    rrf_score: float = 0.0
    rerank_score: float | None = None


class DenseResultItem(BaseModel):
    """向量库原始召回（与 Milvus 返回字段对齐）。"""
    chunk_id: str
    doc_id: str
    source_file: str
    title_path: list[str] = Field(default_factory=list)
    page: int | None = None
    content: str
    score: float       # Milvus distance
    rank: int


class DebugTraceResponse(BaseModel):
    query: str
    rewritten_query: str = ""
    embedding_dim: int = 0
    embedding_preview: list[float] = Field(default_factory=list)

    # 阶段 1：向量库原始召回
    dense_results: list[DenseResultItem] = Field(default_factory=list)
    dense_count: int = 0
    has_sparse: bool = False

    # 阶段 2：RRF 融合
    rrf_candidates: list[CandidateItem] = Field(default_factory=list)
    rrf_count: int = 0

    # 阶段 3：Rerank 精排
    rerank_candidates: list[CandidateItem] = Field(default_factory=list)
    rerank_degraded: bool = False
    rerank_count: int = 0

    # 阶段 4：最终输出（阈值过滤后）
    final_candidates: list[CandidateItem] = Field(default_factory=list)
    final_count: int = 0
    threshold_applied: float = 0.0

    # 阶段 5：组装后的 LLM Prompt（真正发给大模型的）
    system_prompt: str = ""
    user_prompt: str = ""
    full_prompt: str = ""


# ---------- 路由 ----------

@router.post("/v1/debug/trace", response_model=DebugTraceResponse)
async def debug_trace(req: DebugTraceRequest, deps: AppDeps = Depends(get_deps)):
    """对给定 query 做一次完整的检索链路调试，返回每阶段的中间数据。"""
    settings = deps.settings
    logger.info("debug trace: query='%s' kbs=%s", req.query[:80], req.kb_ids)

    # 0. Embedding
    embedded = await asyncio.to_thread(deps.embedder.embed_texts, [req.query], True)
    query_vec = embedded.dense[0]
    sparse_vec = embedded.sparse[0] if embedded.sparse else {}

    # 阶段 1：向量库原始召回（稠密 + 稀疏，不过滤阈值）
    dense_hits = await asyncio.to_thread(
        deps.store.search_dense, req.kb_ids, query_vec,
        max(req.dense_top_k, req.sparse_top_k)  # 多拉点给 debug 看
    )
    has_sparse = bool(sparse_vec) and any(v != 0.0 for v in sparse_vec.values())

    dense_results: list[DenseResultItem] = []
    for h in dense_hits:
        meta = h.metadata or {}
        dense_results.append(DenseResultItem(
            chunk_id=h.chunk_id, doc_id=h.doc_id,
            source_file=meta.get("source_file", ""),
            title_path=meta.get("title_path") or [],
            page=meta.get("page"),
            content=h.content[:3000],  # 前端显示截断
            score=h.score, rank=h.rank,
        ))

    # 阶段 2：RRF 融合（走 retriever 的 RRF）
    candidates = await hybrid_retrieve(
        deps.store, deps.embedder, req.kb_ids, req.query,
        settings, req.dense_top_k, req.sparse_top_k,
    )

    rrf_items: list[CandidateItem] = []
    for c in candidates:
        meta = c.metadata or {}
        rrf_items.append(CandidateItem(
            chunk_id=c.chunk_id, doc_id=c.doc_id,
            source_file=meta.get("source_file", ""),
            title_path=meta.get("title_path") or [],
            page=meta.get("page"),
            content=c.content[:3000],
            dense_rank=c.dense_rank, sparse_rank=c.sparse_rank,
            rrf_score=c.rrf_score,
        ))

    # 阶段 3：Rerank 精排
    top_n = req.rerank_top_n or settings.rerank_top_n
    ranked = await rank_candidates(req.query, candidates, deps.reranker, top_n)

    rerank_items: list[CandidateItem] = []
    for c in ranked.selected:
        meta = c.metadata or {}
        rerank_items.append(CandidateItem(
            chunk_id=c.chunk_id, doc_id=c.doc_id,
            source_file=meta.get("source_file", ""),
            title_path=meta.get("title_path") or [],
            page=meta.get("page"),
            content=c.content[:3000],
            dense_rank=c.dense_rank, sparse_rank=c.sparse_rank,
            rrf_score=c.rrf_score, rerank_score=c.rerank_score,
        ))

    # 阶段 4：阈值过滤
    threshold = req.score_threshold or settings.score_threshold
    final_items = [
        c for c in rerank_items
        if c.rerank_score is not None and c.rerank_score >= threshold
    ] if not ranked.rerank_degraded else rerank_items[:top_n]

    # 阶段 5：组装 Prompt（真正给 LLM 的）
    final_candidates_for_prompt = ranked.selected[:top_n]
    if not ranked.rerank_degraded:
        final_candidates_for_prompt = [
            c for c in ranked.selected
            if c.rerank_score is not None and c.rerank_score >= threshold
        ]
    kept = trim_contexts(final_candidates_for_prompt, settings.context_token_budget)
    citations = build_citations(kept)

    contexts = "\n\n".join(
        _format_context_block(i + 1, c)
        for i, c in enumerate(kept)
    )
    system_prompt = SYSTEM_PROMPT.format(contexts=contexts)
    user_prompt = req.query
    full_prompt = f"【System Prompt】\n{system_prompt}\n\n【User Message】\n{user_prompt}"

    return DebugTraceResponse(
        query=req.query,
        rewritten_query=req.query,
        embedding_dim=len(query_vec),
        embedding_preview=query_vec[:8],
        dense_results=dense_results,
        dense_count=len(dense_results),
        has_sparse=has_sparse,
        rrf_candidates=rrf_items,
        rrf_count=len(rrf_items),
        rerank_candidates=rerank_items,
        rerank_degraded=ranked.rerank_degraded,
        rerank_count=len(rerank_items),
        final_candidates=final_items,
        final_count=len(final_items),
        threshold_applied=threshold if not ranked.rerank_degraded else 0.0,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        full_prompt=full_prompt,
    )


# ---------- 文档存储格式查询 ----------

class StoredChunkItem(BaseModel):
    chunk_id: str
    kb_id: str
    doc_id: str
    content: str
    dense_dim: int
    dense_preview: list[float] = Field(default_factory=list)
    sparse_keys: int = 0
    metadata: dict = Field(default_factory=dict)
    parent_id: str = ""


class DocChunksResponse(BaseModel):
    doc_id: str
    kb_id: str
    chunk_count: int
    chunks: list[StoredChunkItem] = Field(default_factory=list)


@router.get("/v1/debug/chunks/{kb_id}/{doc_id}", response_model=DocChunksResponse)
async def debug_chunks(kb_id: str, doc_id: str, deps: AppDeps = Depends(get_deps)):
    """查看某个文档在向量库中的存储格式（chunk 切分 + embedding + metadata）。"""
    # 用稠密检索方式拉取指定 doc 的所有 chunk
    # 用一个伪向量检索，然后按 doc_id 过滤（Milvus 支持 filter 但 search 必须传向量）
    # 这里用零向量近似：拉尽可能多的候选，再按 doc_id 过滤
    import numpy as np
    dummy_vec = np.zeros(1024, dtype=np.float32).tolist()

    try:
        hits = await asyncio.to_thread(
            deps.store.search_dense, [kb_id], dummy_vec, 200
        )
    except Exception:
        hits = []

    # 过滤出目标 doc 的 chunk
    doc_hits = [h for h in hits if h.doc_id == doc_id]
    chunks: list[StoredChunkItem] = []
    for i, h in enumerate(doc_hits):
        meta = h.metadata or {}
        chunks.append(StoredChunkItem(
            chunk_id=h.chunk_id,
            kb_id=kb_id,
            doc_id=h.doc_id,
            content=h.content[:5000],
            dense_dim=1024,
            dense_preview=[],
            sparse_keys=0,
            metadata=meta,
        ))

    return DocChunksResponse(
        doc_id=doc_id,
        kb_id=kb_id,
        chunk_count=len(chunks),
        chunks=chunks,
    )
