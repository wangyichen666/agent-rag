"""问答与检索路由。"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import AppDeps, get_deps
from app.core.security import verify_internal_token
from app.rag.retriever import hybrid_retrieve, rank_candidates
from app.schemas import (ChatRequest, RetrieveRequest, RetrieveResponse,
                         RetrieveResultItem)
from app.services.chat_service import chat_event_stream

router = APIRouter(dependencies=[Depends(verify_internal_token)])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # 禁止反向代理缓冲
}


@router.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest, deps: AppDeps = Depends(get_deps)):
    return StreamingResponse(
        chat_event_stream(req, deps),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post("/v1/retrieve", response_model=RetrieveResponse)
async def retrieve(req: RetrieveRequest, deps: AppDeps = Depends(get_deps)):
    settings = deps.settings
    candidates = await hybrid_retrieve(
        deps.store, deps.embedder, req.kb_ids, req.query, settings,
        req.dense_top_k or settings.dense_top_k,
        req.sparse_top_k or settings.sparse_top_k,
    )
    top_n = req.rerank_top_n or settings.rerank_top_n
    ranked = await rank_candidates(req.query, candidates, deps.reranker, top_n)
    return RetrieveResponse(results=[
        RetrieveResultItem(
            chunk_id=c.chunk_id,
            content=c.content,
            rerank_score=c.rerank_score if c.rerank_score is not None else c.rrf_score,
            dense_rank=c.dense_rank,
            sparse_rank=c.sparse_rank,
            metadata=c.metadata,
        )
        for c in ranked.selected
    ])
