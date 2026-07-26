"""Rerank 层：bge-reranker-v2-m3（cross-encoder），sigmoid 归一化。

任何环节失败都返回 None，由调用方降级为 RRF 分数排序（见 02 文档 6.3）。
"""
from __future__ import annotations

import logging
import math

from app.core.config import Settings

logger = logging.getLogger(__name__)


class BgeReranker:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = None
        self._load_failed = False

    def _load(self) -> bool:
        if self._model is not None:
            return True
        if self._load_failed:
            return False
        try:
            from FlagEmbedding import FlagReranker  # 延迟导入

            logger.info("loading reranker %s", self._settings.reranker_model_name)
            self._model = FlagReranker(self._settings.reranker_model_name, use_fp16=True)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("reranker load failed, will degrade: %s", exc)
            self._load_failed = True
            return False

    @staticmethod
    def _sigmoid(x: float) -> float:
        return 1.0 / (1.0 + math.exp(-x))

    def rerank(self, query: str, contents: list[str]) -> list[float] | None:
        """返回与 contents 等长的归一化分数；不可用时返回 None。"""
        if not self._settings.reranker_enabled or not contents:
            return None
        if not self._load():
            return None
        try:
            pairs = [[query, c] for c in contents]
            raw = self._model.compute_score(
                pairs, batch_size=16, max_length=self._settings.reranker_max_length
            )
            if isinstance(raw, (int, float)):
                raw = [raw]
            return [self._sigmoid(float(s)) for s in raw]
        except Exception as exc:  # noqa: BLE001
            logger.warning("rerank inference failed, degrade to rrf order: %s", exc)
            return None

    def health(self) -> str:
        if not self._settings.reranker_enabled:
            return "disabled"
        try:
            scores = self.rerank("健康检查", ["这是一个健康检查测试段落。"])
            return "ok" if scores else "error"
        except Exception as exc:  # noqa: BLE001
            return f"error: {exc}"


def build_reranker(settings: Settings) -> BgeReranker:
    return BgeReranker(settings)
