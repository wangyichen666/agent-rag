"""问答编排：改写 → 混合检索 → Rerank → 阈值判断 → Prompt → LLM 流式。

产出 SSE 事件序列（meta / token / done / error），契约见《03-服务接口设计》A.1。
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncIterator

from app.rag.generator import (build_citations, build_messages, rewrite_query,
                               trim_contexts)
from app.rag.retriever import hybrid_retrieve, rank_candidates
from app.schemas import ChatRequest, RetrievalDebug

logger = logging.getLogger(__name__)


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def sse_error(code: str, message: str) -> str:
    return sse("error", {"code": code, "message": message})


async def chat_event_stream(req: ChatRequest, deps) -> AsyncIterator[str]:
    settings = deps.settings
    t0 = time.monotonic()
    options = req.options

    dense_top_k = options.dense_top_k or settings.dense_top_k
    sparse_top_k = options.sparse_top_k or settings.sparse_top_k
    top_n = options.rerank_top_n or settings.rerank_top_n
    threshold = options.score_threshold if options.score_threshold is not None else settings.score_threshold
    temperature = options.temperature if options.temperature is not None else settings.temperature
    max_tokens = options.max_tokens or settings.max_tokens

    try:
        # 1. 改写与 embedding 可并行：改写结果才用于检索，先改写
        rewritten = await rewrite_query(deps.llm, req.question, req.history,
                                        settings, options.rewrite_query)
        if rewritten != req.question:
            logger.info("chat: query rewritten '%s...' -> '%s...'", req.question[:50], rewritten[:50])

        # 2. 混合检索
        candidates = await hybrid_retrieve(deps.store, deps.embedder, req.kb_ids,
                                           rewritten, settings, dense_top_k, sparse_top_k)
        dense_hits = sum(1 for c in candidates if c.dense_rank is not None)
        sparse_hits = sum(1 for c in candidates if c.sparse_rank is not None)
        logger.info("chat: retrieved %d candidates (dense=%d, sparse=%d)", len(candidates), dense_hits, sparse_hits)

        # 3. Rerank 精排
        ranked = await rank_candidates(rewritten, candidates, deps.reranker, top_n)
        logger.info("chat: reranked to %d, top_score=%.4f, degraded=%s", len(ranked.selected),
                    ranked.rerank_scores[0] if ranked.rerank_scores else 0.0, ranked.rerank_degraded)

        # 4. 阈值判断（降级模式不做分数阈值，rrf 分数与阈值不可比）
        no_context = not ranked.selected
        if not no_context and not ranked.rerank_degraded:
            if max(ranked.rerank_scores or [0.0]) < threshold:
                no_context = True

        debug = RetrievalDebug(
            rewritten_query=rewritten, dense_hits=dense_hits,
            sparse_hits=sparse_hits, rerank_scores=ranked.rerank_scores,
        )

        # 5. 拒答分支
        if no_context:
            yield sse("meta", {
                "session_id": req.session_id, "rewritten_query": rewritten,
                "citations": [], "no_relevant_context": True,
            })
            yield sse("token", {"delta": settings.no_context_answer})
            yield sse("done", {
                "finish_reason": "no_context", "usage": None,
                "latency_ms": _elapsed_ms(t0), "retrieval": debug.model_dump(),
            })
            return

        # 6. 上下文预算与引用
        kept = trim_contexts(ranked.selected, settings.context_token_budget)
        citations = [c.model_dump() for c in build_citations(kept)]
        yield sse("meta", {
            "session_id": req.session_id, "rewritten_query": rewritten,
            "citations": citations, "no_relevant_context": False,
        })

        # 7. 流式生成
        messages = build_messages(req.question, kept, req.history)
        async for piece in deps.llm.chat_stream(messages, temperature, max_tokens):
            yield sse("token", {"delta": piece})
            await asyncio.sleep(0)  # 让出事件循环，及时冲刷

        yield sse("done", {
            "finish_reason": "stop", "usage": None,
            "latency_ms": _elapsed_ms(t0), "retrieval": debug.model_dump(),
        })

    except Exception as exc:  # noqa: BLE001
        logger.exception("chat stream failed")
        yield sse_error("INTERNAL_ERROR", str(exc))


def _elapsed_ms(t0: float) -> int:
    return int((time.monotonic() - t0) * 1000)
