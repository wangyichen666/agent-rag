"""生成层：Query 改写、Prompt 组装（编号引用 + token 预算）、OpenAI 兼容流式调用。"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx

from app.core.config import Settings
from app.rag.chunkers import estimate_tokens
from app.rag.retriever import Candidate
from app.schemas import Citation, HistoryMessage

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个严谨的企业知识库助手。基于「参考资料」回答用户问题。

要求：
1. 只依据参考资料回答，资料中没有的内容，明确说"根据现有资料无法回答"，不要编造。
2. 回答中引用资料时，在对应语句末尾标注引用编号，格式 [1] [2]。
3. 回答使用简体中文，结构清晰，必要时使用列表。
4. 不要复述参考资料全文，用自己的话归纳。

【参考资料】
{contexts}"""

REWRITE_PROMPT = """你是检索查询改写助手。根据对话历史，把用户的最新问题改写成一个独立、完整、适合检索的问题。
只输出改写后的问题本身，不要输出任何解释。如果原问题已经足够独立完整，原样输出。

【对话历史】
{history}

【最新问题】
{question}

【改写结果】"""


class LlmClient:
    """OpenAI 兼容协议客户端（DeepSeek / 通义 / vLLM 均可接入）。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.llm_base_url.rstrip("/"),
                headers={"Authorization": f"Bearer {self._settings.llm_api_key}"},
                timeout=httpx.Timeout(self._settings.llm_timeout_s, connect=10.0),
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def chat_once(self, messages: list[dict], model: str | None = None,
                        temperature: float = 0.1, max_tokens: int = 256) -> str:
        """非流式调用（query 改写等场景）。"""
        payload = {
            "model": model or self._settings.llm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        resp = await self._get_client().post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return (data["choices"][0]["message"]["content"] or "").strip()

    async def chat_stream(self, messages: list[dict], temperature: float,
                          max_tokens: int) -> AsyncIterator[str]:
        """流式调用，逐 delta 产出文本。"""
        payload = {
            "model": self._settings.llm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        async with self._get_client().stream("POST", "/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                piece = delta.get("content")
                if piece:
                    yield piece

    async def health(self) -> str:
        try:
            await self.chat_once(
                [{"role": "user", "content": "ping, reply with one word"}],
                temperature=0.0, max_tokens=8,
            )
            return "ok"
        except Exception as exc:  # noqa: BLE001
            return f"error: {exc}"


# ------------------------------------------------------------------ 改写

async def rewrite_query(llm: LlmClient, question: str, history: list[HistoryMessage],
                        settings: Settings, enabled: bool) -> str:
    """多轮指代消解：有历史才改写；失败时返回原问题（不阻塞主流程）。"""
    if not enabled or not settings.rewrite_enabled or not history:
        return question
    recent = history[- settings.rewrite_max_history_rounds * 2:]
    history_text = "\n".join(f"{'用户' if m.role == 'user' else '助手'}：{m.content}" for m in recent)
    try:
        rewritten = await llm.chat_once(
            [{"role": "user", "content": REWRITE_PROMPT.format(history=history_text, question=question)}],
            model=settings.rewrite_model or None,
            temperature=0.0, max_tokens=128,
        )
        return rewritten or question
    except Exception as exc:  # noqa: BLE001
        logger.warning("query rewrite failed, use original: %s", exc)
        return question


# ------------------------------------------------------------------ Prompt 组装

def build_citations(selected: list[Candidate]) -> list[Citation]:
    citations: list[Citation] = []
    for i, c in enumerate(selected, start=1):
        meta = c.metadata or {}
        citations.append(Citation(
            ref_id=i,
            chunk_id=c.chunk_id,
            doc_id=c.doc_id,
            source_file=meta.get("source_file", ""),
            page=meta.get("page"),
            title_path=meta.get("title_path") or [],
            score=c.rerank_score or 0.0,
        ))
    return citations


def _format_context_block(ref_id: int, c: Candidate) -> str:
    meta = c.metadata or {}
    source = meta.get("source_file", "未知来源")
    page = f" 第{meta['page']}页" if meta.get("page") else ""
    path = " / ".join(meta.get("title_path") or [])
    path = f" · {path}" if path else ""
    return f"[{ref_id}]（来源：{source}{page}{path}）\n{c.content}"


def trim_contexts(selected: list[Candidate], budget_tokens: int) -> list[Candidate]:
    """按分数从高到低装入预算，超出则从低分开始丢弃。"""
    kept: list[Candidate] = []
    used = 0
    for c in selected:
        cost = estimate_tokens(c.content) + 30  # 30: 来源行开销
        if kept and used + cost > budget_tokens:
            continue
        kept.append(c)
        used += cost
    return kept


def build_messages(question: str, kept: list[Candidate], history: list[HistoryMessage],
                   max_history_rounds: int = 5) -> list[dict]:
    contexts = "\n\n".join(_format_context_block(i, c) for i, c in enumerate(kept, start=1))
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT.format(contexts=contexts)}]
    for m in history[- max_history_rounds * 2:]:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": question})
    return messages
