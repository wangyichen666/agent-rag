"""图检索：问题实体 → 子图扩展（1..max_hops）→ 命中块候选。"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from app.core.config import Settings
from app.rag.extractor import extract_query_entities
from app.rag.generator import LlmClient
from app.rag.graph_store import GraphStore

logger = logging.getLogger(__name__)


@dataclass
class GraphCandidate:
    chunk_id: str
    doc_id: str
    content: str
    metadata: dict = field(default_factory=dict)
    hop: int = 1
    score: float = 0.0


@dataclass
class GraphRetrieveResult:
    """图检索结果：匹配到的实体 + 命中块 + 跳过原因（用于追溯页展示）。"""
    entities: list[str] = field(default_factory=list)
    hits: list[GraphCandidate] = field(default_factory=list)
    skipped: str = ""


async def graph_retrieve(graph_store: GraphStore, llm: LlmClient,
                         kb_ids: list[str], query: str, settings: Settings,
                         top_k: int | None = None) -> GraphRetrieveResult:
    """图通道检索。任何一步失败都返回空结果 + skipped 原因（不影响向量通道）。"""
    if not settings.graph_enabled or not kb_ids:
        return GraphRetrieveResult(skipped="知识图谱功能未开启")
    try:
        names = await extract_query_entities(llm, query, settings)
        matched = await asyncio.to_thread(graph_store.match_entities, kb_ids, names) if names else []
        if not matched:
            # LLM 实体没对上图：文本包含兜底（实体名直接出现在问题里）
            matched = await asyncio.to_thread(
                graph_store.fallback_match_entities, kb_ids, query, 10
            )
        if not matched:
            logger.info("graph retrieve: no matched entities for query '%.60s'", query)
            return GraphRetrieveResult(
                entities=names,
                skipped="未匹配到知识库中的实体（图谱无命中）",
            )
        hits = await asyncio.to_thread(
            graph_store.search, kb_ids, matched,
            settings.graph_max_hops, top_k or settings.graph_top_k,
        )
        logger.info("graph retrieve: entities=%s hits=%d", matched, len(hits))
        return GraphRetrieveResult(
            entities=matched,
            hits=[
                GraphCandidate(
                    chunk_id=h.chunk_id, doc_id=h.doc_id, content=h.content,
                    metadata=h.metadata, hop=h.hop, score=h.score,
                )
                for h in hits
            ],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("graph retrieve failed (degrade to vector-only): %s", exc)
        return GraphRetrieveResult(skipped=f"图谱检索异常（已降级为纯向量）: {exc}")
