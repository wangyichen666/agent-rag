"""文档入库编排：拉文件 → 解析 → 切分 → Embedding → 写向量库 → 回调 Java。

任务状态保存在内存注册表（一期单副本够用；二期 MQ 化时替换为持久化队列）。
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid

import httpx

from app.rag.chunkers import chunk_document
from app.rag.parsers import parse_document
from app.rag.vector_store import StoredChunk
from app.schemas import IngestCallback, IngestRequest, IngestStatus

logger = logging.getLogger(__name__)

EMBED_BATCH = 64


class TaskRegistry:
    def __init__(self) -> None:
        self._tasks: dict[str, IngestStatus] = {}

    def create(self, doc_id: str) -> str:
        task_id = uuid.uuid4().hex[:16]
        self._tasks[task_id] = IngestStatus(task_id=task_id, doc_id=doc_id, status="processing")
        logger.info("ingest task created: task_id=%s doc_id=%s", task_id, doc_id)
        return task_id

    def update(self, task_id: str, **fields) -> None:
        task = self._tasks.get(task_id)
        if task:
            for k, v in fields.items():
                setattr(task, k, v)

    def get(self, task_id: str) -> IngestStatus | None:
        return self._tasks.get(task_id)


registry = TaskRegistry()


async def run_ingest(req: IngestRequest, deps) -> None:
    """后台任务主体。任何异常都收敛为 failed 状态并回调。"""
    task_id = next((t.task_id for t in registry._tasks.values() if t.doc_id == req.doc_id), "")
    t0 = time.monotonic()
    settings = deps.settings
    logger.info("ingest %s: starting, file=%s type=%s", req.doc_id, req.file.name, req.file.type)

    try:
        # 1. 拉取文件（trust_env=False 绕过系统代理，直连 MinIO）
        logger.debug("ingest %s: downloading from %s", req.doc_id, req.file.url)
        async with httpx.AsyncClient(
            trust_env=False, timeout=httpx.Timeout(300.0, connect=10.0)
        ) as client:
            resp = await client.get(req.file.url)
            resp.raise_for_status()
            data = resp.content
        logger.info("ingest %s: fetched %d bytes", req.doc_id, len(data))

        # 2. 解析（线程池，避免阻塞事件循环）
        logger.debug("ingest %s: parsing with parser=%s", req.doc_id, req.parser)
        t_parse = time.monotonic()
        parsed = await asyncio.to_thread(
            parse_document, data, req.file.type, req.file.name, req.parser
        )
        logger.info("ingest %s: parsed in %.1fs, source=%s, blocks=%d", req.doc_id,
                     time.monotonic() - t_parse, parsed.source_name, len(parsed.blocks))

        # 3. 切分
        cfg = req.chunk_config
        logger.debug("ingest %s: chunking with strategy=%s", req.doc_id, cfg.strategy)
        chunks = await asyncio.to_thread(
            chunk_document, parsed, cfg.strategy,
            cfg.chunk_size or settings.chunk_size,
            cfg.chunk_overlap if cfg.chunk_overlap is not None else settings.chunk_overlap,
            settings.min_chunk_size,
        )
        logger.info("ingest %s: %d chunks produced", req.doc_id, len(chunks))
        if not chunks:
            raise ValueError("document produced zero chunks after parsing")

        # 4. Embedding（分批）
        texts = [c.content for c in chunks]
        dense_all: list[list[float]] = []
        sparse_all: list[dict[int, float]] = []
        logger.debug("ingest %s: embedding %d texts in batches of %d", req.doc_id, len(texts), EMBED_BATCH)
        for i in range(0, len(texts), EMBED_BATCH):
            batch = texts[i: i + EMBED_BATCH]
            result = await asyncio.to_thread(deps.embedder.embed_texts, batch, False)
            dense_all.extend(result.dense)
            sparse_all.extend(result.sparse)
        logger.info("ingest %s: embedded %d vectors, dim=%d", req.doc_id, len(dense_all),
                     len(dense_all[0]) if dense_all else 0)

        # 5. 入库（先删旧版本，保证幂等）
        logger.debug("ingest %s: upserting to vector store", req.doc_id)
        await asyncio.to_thread(deps.store.delete_doc, req.kb_id, req.doc_id)
        stored = [
            StoredChunk(
                kb_id=req.kb_id, doc_id=req.doc_id,
                chunk_id=f"{req.doc_id}-{c.chunk_index}",
                content=c.content, dense=dense_all[i], sparse=sparse_all[i],
                parent_id=c.parent_id or "",
                metadata={
                    "source_file": req.file.name,
                    "page": c.page,
                    "title_path": c.title_path,
                    "content_type": c.content_type,
                    "chunk_index": c.chunk_index,
                },
            )
            for i, c in enumerate(chunks)
        ]
        await asyncio.to_thread(deps.store.upsert, stored)

        elapsed = int((time.monotonic() - t0) * 1000)
        registry.update(task_id, status="success", chunk_count=len(stored))
        await _callback(req, IngestCallback(doc_id=req.doc_id, status="success",
                                            chunk_count=len(stored), elapsed_ms=elapsed))
        logger.info("ingest %s: success, %d chunks, %dms", req.doc_id, len(stored), elapsed)

    except Exception as exc:  # noqa: BLE001
        logger.exception("ingest %s failed", req.doc_id)
        elapsed = int((time.monotonic() - t0) * 1000)
        err_msg = str(exc)[:500]
        registry.update(task_id, status="failed", error=err_msg)
        await _callback(req, IngestCallback(doc_id=req.doc_id, status="failed",
                                            elapsed_ms=elapsed, error=err_msg))


async def _callback(req: IngestRequest, payload: IngestCallback) -> None:
    if not req.callback_url:
        logger.debug("ingest %s: no callback_url, skip", req.doc_id)
        return
    try:
        logger.debug("ingest %s: callback to %s status=%s", req.doc_id, req.callback_url, payload.status)
        async with httpx.AsyncClient(trust_env=False, timeout=15.0) as client:
            await client.post(req.callback_url, json=payload.model_dump())
        logger.debug("ingest %s: callback sent", req.doc_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ingest callback failed for %s: %s", req.doc_id, exc)
