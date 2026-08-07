"""LLM 实体/关系抽取：文档块 → 三元组；问题 → 实体名。

输出契约全部是严格 JSON，解析带容错（代码块围栏、前后杂文、截断）。
抽取失败只记日志并降级，绝不阻塞入库/问答主流程。
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from app.core.config import Settings
from app.rag.generator import LlmClient

logger = logging.getLogger(__name__)


@dataclass
class Triple:
    head: str
    relation: str
    tail: str
    head_type: str = ""
    tail_type: str = ""
    chunk_id: str = ""


BATCH_EXTRACT_PROMPT = """你是一个知识图谱实体抽取器。请从下面编号的文本块中抽取实体三元组。

要求：
1. 只抽取文本中明确出现的实体与关系，不要编造或泛化。
2. 实体名保持原文用词（例如 Milvus、Java 业务层），不要同义改写。
3. 关系使用简短动词短语（例如 属于、依赖、负责、发布于、使用）。
4. 一个文本块最多输出 12 条三元组。
5. 只输出 JSON 数组，不要输出任何解释文字。

【文本块】
{blocks}

【输出格式】
[{{"chunk_index":1,"head":"实体A","relation":"关系","tail":"实体B","head_type":"类型","tail_type":"类型"}}]"""


QUERY_ENTITY_PROMPT = """从用户问题中抽取关键实体（人名、机构名、产品名、系统名、专有名词）。
只输出 JSON 字符串数组，例如 ["Milvus"]。不要输出任何解释文字。

【问题】
{question}

【输出】"""


def _clean(value: str, max_len: int = 100) -> str:
    value = (value or "").strip().strip('"').strip("'").strip()
    return value[:max_len]


def parse_json_array(raw: str) -> list:
    """从 LLM 输出中解析 JSON 数组，容忍围栏/前后杂文/截断。"""
    if not raw:
        return []
    text = raw.strip()
    # 去掉 ```json ... ``` 围栏
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE).strip()
    text = re.sub(r"\s*```$", "", text).strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        logger.debug("no json array found in LLM output: %.200s", raw)
        return []
    try:
        parsed = json.loads(text[start:end + 1])
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        logger.debug("json parse failed: %.200s", raw)
        return []


async def extract_triples_batch(llm: LlmClient,
                                items: list[tuple[str, str]],
                                settings: Settings) -> dict[str, list[Triple]]:
    """按 chunk (chunk_id, content) 分批抽取，返回 chunk_id -> [Triple]。

    items 为空时返回 {}；单批解析失败只跳过该批。
    """
    out: dict[str, list[Triple]] = {}
    if not items:
        return out
    batch_size = max(1, settings.graph_extract_batch_size)
    model = settings.graph_extract_model or None

    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        blocks = "\n".join(f"[{j + 1}] {content}" for j, (_, content) in enumerate(batch))
        prompt = BATCH_EXTRACT_PROMPT.format(blocks=blocks)
        try:
            raw = await llm.chat_once(
                [{"role": "user", "content": prompt}],
                model=model, temperature=0.0, max_tokens=2048,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("graph extraction batch failed (skip): %s", exc)
            continue

        triples = parse_json_array(raw)
        for item in triples:
            if not isinstance(item, dict):
                continue
            idx = item.get("chunk_index")
            if not isinstance(idx, int) or not (1 <= idx <= len(batch)):
                continue
            chunk_id, _ = batch[idx - 1]
            head = _clean(item.get("head"))
            relation = _clean(item.get("relation"), 60)
            tail = _clean(item.get("tail"))
            if not head or not tail or head == tail:
                continue
            out.setdefault(chunk_id, []).append(Triple(
                head=head, relation=relation or "相关", tail=tail,
                head_type=_clean(item.get("head_type"), 30),
                tail_type=_clean(item.get("tail_type"), 30),
                chunk_id=chunk_id,
            ))
    return out


async def extract_query_entities(llm: LlmClient, question: str,
                                 settings: Settings) -> list[str]:
    """从问题抽取实体名；失败返回 []（调用方走文本包含兜底）。"""
    try:
        raw = await llm.chat_once(
            [{"role": "user", "content": QUERY_ENTITY_PROMPT.format(question=question)}],
            model=settings.graph_extract_model or None,
            temperature=0.0, max_tokens=128,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("query entity extraction failed: %s", exc)
        return []
    names: list[str] = []
    for item in parse_json_array(raw):
        if isinstance(item, str):
            name = _clean(item)
            if name:
                names.append(name)
    return names[:20]
