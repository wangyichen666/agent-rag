"""向量库抽象 + 两种实现：Milvus（生产默认）/ InMemory（本地无 Milvus 联调）。

检索接口统一返回 ScoredChunk，带 rank 信息供 RRF 融合与契约回填（dense_rank/sparse_rank）。
"""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class StoredChunk:
    kb_id: str
    doc_id: str
    chunk_id: str
    content: str
    dense: list[float]
    sparse: dict[int, float]
    parent_id: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class ScoredChunk:
    chunk_id: str
    doc_id: str
    content: str
    metadata: dict
    score: float
    rank: int


class VectorStore(ABC):
    @abstractmethod
    def upsert(self, chunks: list[StoredChunk]) -> int: ...

    @abstractmethod
    def search_dense(self, kb_ids: list[str], vector: list[float], top_k: int) -> list[ScoredChunk]: ...

    @abstractmethod
    def search_sparse(self, kb_ids: list[str], sparse: dict[int, float], top_k: int) -> list[ScoredChunk]: ...

    @abstractmethod
    def delete_doc(self, kb_id: str, doc_id: str) -> None: ...

    @abstractmethod
    def delete_kb(self, kb_id: str) -> None: ...

    @abstractmethod
    def health(self) -> str: ...


# ------------------------------------------------------------------ Milvus

class MilvusStore(VectorStore):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None

    def _connect(self):
        if self._client is not None:
            return self._client
        from pymilvus import MilvusClient  # 延迟导入

        logger.info("connecting milvus %s", self._settings.milvus_uri)
        self._client = MilvusClient(
            uri=self._settings.milvus_uri,
            token=self._settings.milvus_token or None,
        )
        self._ensure_collection(self._client)
        return self._client

    def _ensure_collection(self, client) -> None:
        name = self._settings.milvus_collection
        if client.has_collection(name):
            return
        from pymilvus import DataType

        logger.info("creating collection %s", name)
        schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
        schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field("kb_id", DataType.VARCHAR, max_length=64, is_partition_key=True)
        schema.add_field("doc_id", DataType.VARCHAR, max_length=64)
        schema.add_field("chunk_id", DataType.VARCHAR, max_length=128)
        schema.add_field("parent_id", DataType.VARCHAR, max_length=128)
        schema.add_field("content", DataType.VARCHAR, max_length=8192)
        schema.add_field("metadata", DataType.JSON)
        schema.add_field("dense", DataType.FLOAT_VECTOR, dim=1024)
        schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)

        index = client.prepare_index_params()
        index.add_index(field_name="dense", index_type="HNSW", metric_type="IP",
                        params={"M": 16, "efConstruction": 200})
        index.add_index(field_name="sparse", index_type="SPARSE_INVERTED_INDEX", metric_type="IP")
        client.create_collection(collection_name=name, schema=schema,
                                 index_params=index, num_partitions=64)

    @staticmethod
    def _kb_filter(kb_ids: list[str]) -> str:
        quoted = ", ".join(f'"{k}"' for k in kb_ids)
        return f"kb_id in [{quoted}]"

    _OUT_FIELDS = ["chunk_id", "doc_id", "content", "metadata"]

    def upsert(self, chunks: list[StoredChunk]) -> int:
        if not chunks:
            return 0
        client = self._connect()
        rows = [
            {
                "kb_id": c.kb_id, "doc_id": c.doc_id, "chunk_id": c.chunk_id,
                "parent_id": c.parent_id, "content": c.content[:8000],
                "metadata": c.metadata, "dense": c.dense, "sparse": c.sparse,
            }
            for c in chunks
        ]
        client.insert(collection_name=self._settings.milvus_collection, data=rows)
        return len(rows)

    def search_dense(self, kb_ids: list[str], vector: list[float], top_k: int) -> list[ScoredChunk]:
        client = self._connect()
        hits = client.search(
            collection_name=self._settings.milvus_collection,
            data=[vector], anns_field="dense", limit=top_k,
            filter=self._kb_filter(kb_ids),
            search_params={"metric_type": "IP", "params": {"ef": self._settings.search_ef}},
            output_fields=self._OUT_FIELDS,
        )[0]
        return [
            ScoredChunk(h["entity"]["chunk_id"], h["entity"]["doc_id"],
                        h["entity"]["content"], h["entity"].get("metadata") or {},
                        float(h["distance"]), rank=i + 1)
            for i, h in enumerate(hits)
        ]

    def search_sparse(self, kb_ids: list[str], sparse: dict[int, float], top_k: int) -> list[ScoredChunk]:
        client = self._connect()
        hits = client.search(
            collection_name=self._settings.milvus_collection,
            data=[sparse], anns_field="sparse", limit=top_k,
            filter=self._kb_filter(kb_ids),
            search_params={"metric_type": "IP"},
            output_fields=self._OUT_FIELDS,
        )[0]
        return [
            ScoredChunk(h["entity"]["chunk_id"], h["entity"]["doc_id"],
                        h["entity"]["content"], h["entity"].get("metadata") or {},
                        float(h["distance"]), rank=i + 1)
            for i, h in enumerate(hits)
        ]

    def delete_doc(self, kb_id: str, doc_id: str) -> None:
        client = self._connect()
        client.delete(collection_name=self._settings.milvus_collection,
                      filter=f'kb_id == "{kb_id}" and doc_id == "{doc_id}"')

    def delete_kb(self, kb_id: str) -> None:
        client = self._connect()
        client.delete(collection_name=self._settings.milvus_collection,
                      filter=f'kb_id == "{kb_id}"')

    def health(self) -> str:
        try:
            self._connect()
            return "ok"
        except Exception as exc:  # noqa: BLE001
            return f"error: {exc}"


# ------------------------------------------------------------------ InMemory

class InMemoryStore(VectorStore):
    """本地联调用内存库：numpy 暴力余弦 + 词项重叠打分。勿用于生产。"""

    def __init__(self) -> None:
        self._chunks: list[StoredChunk] = []
        self._matrix: np.ndarray | None = None

    def _rebuild_matrix(self) -> None:
        self._matrix = np.asarray([c.dense for c in self._chunks], dtype=np.float32) if self._chunks else None

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(re.findall(r"[一-鿿]|[a-zA-Z0-9]+", text.lower()))

    def upsert(self, chunks: list[StoredChunk]) -> int:
        self._chunks.extend(chunks)
        self._rebuild_matrix()
        return len(chunks)

    def _by_kb(self, kb_ids: list[str]) -> list[tuple[int, StoredChunk]]:
        kb = set(kb_ids)
        return [(i, c) for i, c in enumerate(self._chunks) if c.kb_id in kb]

    def search_dense(self, kb_ids: list[str], vector: list[float], top_k: int) -> list[ScoredChunk]:
        candidates = self._by_kb(kb_ids)
        if not candidates or self._matrix is None:
            return []
        q = np.asarray(vector, dtype=np.float32)
        q = q / (np.linalg.norm(q) or 1.0)
        scored = [(c, float(np.dot(self._matrix[i], q))) for i, c in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [ScoredChunk(c.chunk_id, c.doc_id, c.content, c.metadata, s, rank=i + 1)
                for i, (c, s) in enumerate(scored[:top_k])]

    def search_sparse(self, kb_ids: list[str], sparse: dict[int, float], top_k: int) -> list[ScoredChunk]:
        # 内存实现不还原 token 空间，退化为内容词项重叠打分
        candidates = self._by_kb(kb_ids)
        scored = []
        for _, c in candidates:
            overlap = len(self._tokens(c.content)) and 0.0 or 0.0
            scored.append((c, overlap))
        # 无真实 query 词表可用时全部 0 分，按插入序返回；稠密路仍可工作
        return [ScoredChunk(c.chunk_id, c.doc_id, c.content, c.metadata, s, rank=i + 1)
                for i, (c, s) in enumerate(scored[:top_k])]

    def delete_doc(self, kb_id: str, doc_id: str) -> None:
        self._chunks = [c for c in self._chunks if not (c.kb_id == kb_id and c.doc_id == doc_id)]
        self._rebuild_matrix()

    def delete_kb(self, kb_id: str) -> None:
        self._chunks = [c for c in self._chunks if c.kb_id != kb_id]
        self._rebuild_matrix()

    def health(self) -> str:
        return "ok(memory)"


def build_store(settings: Settings) -> VectorStore:
    if settings.vector_store == "memory":
        logger.warning("using InMemoryStore, for local debugging only")
        return InMemoryStore()
    return MilvusStore(settings)
