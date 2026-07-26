"""Embedding 层：BGE-M3（稠密 + 稀疏），懒加载 + hash LRU 缓存。

- query 侧加指令前缀，passage 侧不加（BGE 系列非对称用法）
- embedding_enabled=false 时切换为确定性伪向量，仅供无模型环境联调
"""
from __future__ import annotations

import hashlib
import logging
import math
from collections import OrderedDict
from dataclasses import dataclass

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
        h = hashlib.sha256(("q:" if is_query else "p:") + text.encode("utf-8")).hexdigest()
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


class BgeM3Embedder:
    """BGE-M3 封装。模型体积大且依赖 torch，首次调用时才加载。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = None
        self._cache = _LruCache(_CACHE_CAPACITY)

    def _load(self) -> None:
        if self._model is not None:
            return
        from FlagEmbedding import BGEM3FlagModel  # 延迟导入重依赖

        device = self._settings.embedding_device
        if device == "auto":
            device = self._detect_device()
        logger.info("loading embedding model %s on %s", self._settings.embedding_model_name, device)
        self._model = BGEM3FlagModel(
            self._settings.embedding_model_name,
            devices=device,
            use_fp16=self._settings.embedding_use_fp16 and device != "cpu",
        )

    @staticmethod
    def _detect_device() -> str:
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    # ------------------------------------------------------------------

    def embed_texts(self, texts: list[str], is_query: bool) -> EmbedResult:
        if not texts:
            return EmbedResult([], [])
        self._load()

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
            outputs = self._model.encode(
                miss_texts,
                batch_size=self._settings.embedding_batch_size,
                max_length=8192,
                instruction=self._settings.embedding_query_instruction if is_query else None,
                return_dense=True,
                return_sparse=True,
                return_colbert_vecs=False,
            )
            dense_vecs = np.asarray(outputs["dense_vecs"], dtype=np.float32)
            dense_vecs = self._normalize(dense_vecs)
            lexical = outputs["lexical_weights"]
            for pos, idx in enumerate(miss_idx):
                dense = dense_vecs[pos].tolist()
                sparse = {int(k): float(v) for k, v in lexical[pos].items()}
                dense_out[idx], sparse_out[idx] = dense, sparse
                self._cache.put(texts[idx], is_query, (dense, sparse))

        return EmbedResult(
            dense=[d for d in dense_out if d is not None],
            sparse=[s for s in sparse_out if s is not None],
        )

    @staticmethod
    def _normalize(vecs: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms

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
    return BgeM3Embedder(settings) if settings.embedding_enabled else FakeEmbedder()
