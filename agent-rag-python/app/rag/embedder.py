"""Embedding 层：SiliconFlow Qwen3-Embedding API + hash LRU 缓存。

SiliconFlow Qwen3-Embedding 仅返回稠密向量（0.6B=1024维），无稀疏/词法权重。
embedding_enabled=false 时切换为确定性伪向量，仅供无模型环境联调。
"""
from __future__ import annotations

import hashlib
import logging
import math
from collections import OrderedDict
from dataclasses import dataclass

import httpx
import numpy as np

from app.core.config import Settings

logger = logging.getLogger(__name__)

DENSE_DIM = 1024
_CACHE_CAPACITY = 4096


@dataclass
class EmbedResult:
    dense: list[list[float]]
    sparse: list[dict[int, float]]


class _LruCache:
    def __init__(self, capacity: int) -> None:
        self._store: OrderedDict[str, tuple[list[float], dict[int, float]]] = OrderedDict()
        self._capacity = capacity

    @staticmethod
    def _key(text: str, is_query: bool) -> str:
        prefix = b"q:" if is_query else b"p:"
        h = hashlib.sha256(prefix + text.encode("utf-8")).hexdigest()
        return h

    def get(self, text: str, is_query: bool):
        key = self._key(text, is_query)
        if key in self._store:
            self._store.move_to_end(key)
            return self._store[key]
        return None

    def put(self, text: str, is_query: bool, value) -> None:
        key = self._key(text, is_query)
        self._store[key] = value
        self._store.move_to_end(key)
        while len(self._store) > self._capacity:
            self._store.popitem(last=False)


class SiliconFlowEmbedder:
    """SiliconFlow Qwen3-Embedding API 封装。仅返回稠密向量，稀疏向量为空 dict。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cache = _LruCache(_CACHE_CAPACITY)

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._settings.siliconflow_api_key}",
            "Content-Type": "application/json",
        }

    @property
    def _embed_url(self) -> str:
        return f"{self._settings.siliconflow_base_url}/embeddings"

    # ------------------------------------------------------------------

    def embed_texts(self, texts: list[str], is_query: bool) -> EmbedResult:
        """批量向量化。is_query 仅用于缓存键区分，API 侧不做特殊处理。"""
        if not texts:
            return EmbedResult([], [])

        dense_out: list[list[float] | None] = [None] * len(texts)
        sparse_out: list[dict[int, float] | None] = [None] * len(texts)
        miss_idx: list[int] = []
        miss_texts: list[str] = []

        for i, t in enumerate(texts):
            hit = self._cache.get(t, is_query)
            if hit is not None:
                dense_out[i], sparse_out[i] = hit
            else:
                miss_idx.append(i)
                miss_texts.append(t)

        if miss_texts:
            logger.debug("embedding %d texts (cache miss %d, model=%s)", len(texts), len(miss_texts),
                         self._settings.embedding_model_name)
            try:
                resp = httpx.post(
                    self._embed_url,
                    headers=self._headers,
                    json={
                        "model": self._settings.embedding_model_name,
                        "input": miss_texts,
                        "encoding_format": "float",
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()["data"]
                logger.debug("embedding OK: %d vectors, dim=%d", len(data), len(data[0]["embedding"]))
            except Exception as exc:  # noqa: BLE001
                logger.error("SiliconFlow embedding API failed: %s", exc)
                raise

            for item in data:
                idx_in_data = item["index"]
                real_idx = miss_idx[idx_in_data]
                vec = np.asarray(item["embedding"], dtype=np.float32)
                vec = self._normalize_single(vec)
                dense = vec.tolist()
                sparse: dict[int, float] = {}
                dense_out[real_idx], sparse_out[real_idx] = dense, sparse
                self._cache.put(texts[real_idx], is_query, (dense, sparse))

        return EmbedResult(
            dense=[d for d in dense_out if d is not None],
            sparse=[s for s in sparse_out if s is not None],
        )

    @staticmethod
    def _normalize_single(vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        return vec / norm if norm != 0 else vec

    def health(self) -> str:
        try:
            self.embed_texts(["health check"], is_query=True)
            return "ok"
        except Exception as exc:  # noqa: BLE001
            logger.warning("embedding health failed: %s", exc)
            return f"error: {exc}"


class FakeEmbedder:
    """无模型联调用：确定性伪向量。向量空间无语义，仅验证链路。"""

    def embed_texts(self, texts: list[str], is_query: bool) -> EmbedResult:
        dense, sparse = [], []
        for t in texts:
            seed = int(hashlib.sha256(t.encode("utf-8")).hexdigest()[:8], 16)
            rng = np.random.default_rng(seed)
            vec = rng.standard_normal(DENSE_DIM).astype(np.float32)
            vec = vec / (np.linalg.norm(vec) or 1.0)
            dense.append(vec.tolist())
            sparse_sparse: dict[int, float] = {}
            for tok in t[:64]:
                idx = int(hashlib.md5(tok.encode("utf-8")).hexdigest()[:6], 16)
                sparse_sparse[idx] = 1.0
            sparse.append(sparse_sparse)
        return EmbedResult(dense, sparse)

    def health(self) -> str:
        return "ok(fake)"


def build_embedder(settings: Settings):
    return SiliconFlowEmbedder(settings) if settings.embedding_enabled else FakeEmbedder()
