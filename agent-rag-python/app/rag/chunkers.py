"""切分器：结构感知优先，递归字符兜底。

产出 Chunk（content + metadata），metadata 字段与《02-RAG核心功能详解》2.6 一致。
token 计数采用近似估算（中文 1 字 ≈ 1 token，英文 4 字符 ≈ 1 token），
避免引入 tokenizer 依赖；误差对切分决策可接受。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.rag.parsers import Block, ParserOutput

DEFAULT_SEPARATORS = ["\n## ", "\n### ", "\n\n", "\n", "。", "；", "，", " "]


def estimate_tokens(text: str) -> int:
    """粗略 token 估算：CJK 按 1 字 1 token，其余按 4 字符 1 token。"""
    cjk = sum(1 for ch in text if "一" <= ch <= "鿿")
    return cjk + (len(text) - cjk) // 4 + 1


@dataclass
class Chunk:
    content: str
    chunk_index: int
    title_path: list[str] = field(default_factory=list)
    page: int | None = None
    content_type: str = "text"
    parent_id: str | None = None
    meta: dict = field(default_factory=dict)


# ------------------------------------------------------------------ 递归切分

def recursive_split(text: str, chunk_size: int, chunk_overlap: int,
                    separators: list[str] | None = None) -> list[str]:
    """按分隔符优先级递归切分，带重叠。"""
    seps = separators or DEFAULT_SEPARATORS
    if estimate_tokens(text) <= chunk_size:
        return [text] if text.strip() else []

    sep = seps[-1]
    for candidate in seps:
        if candidate in text:
            sep = candidate
            break

    pieces = text.split(sep)
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        candidate = (current + sep + piece) if current else piece
        if estimate_tokens(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if estimate_tokens(piece) > chunk_size:
                # 单段仍超长：降一级分隔符继续递归
                deeper = [s for s in seps if s != sep]
                chunks.extend(recursive_split(piece, chunk_size, chunk_overlap, deeper))
                current = ""
            else:
                current = piece
    if current:
        chunks.append(current)

    if chunk_overlap > 0 and len(chunks) > 1:
        chunks = _apply_overlap(chunks, chunk_overlap)
    return chunks


def _apply_overlap(chunks: list[str], overlap: int) -> list[str]:
    """把前一块尾部约 overlap token 的文本拼到下一块头部。"""
    out = [chunks[0]]
    for prev, cur in zip(chunks, chunks[1:]):
        tail = _tail_tokens(prev, overlap)
        out.append((tail + cur) if tail else cur)
    return out


def _tail_tokens(text: str, tokens: int) -> str:
    """取尾部约 tokens 个 token 的原文（按字符近似截取，避免切断词）。"""
    if not text:
        return ""
    approx_chars = tokens  # CJK 场景 1 token ≈ 1 字，保守按字数
    if len(text) <= approx_chars:
        return text
    tail = text[-approx_chars:]
    first_break = tail.find("。")
    if 0 <= first_break < len(tail) - 1:
        tail = tail[first_break + 1:]
    return tail


# ------------------------------------------------------------------ 结构切分

def structure_chunks(doc: ParserOutput, chunk_size: int, chunk_overlap: int,
                     min_chunk_size: int, doc_id: str = "") -> list[Chunk]:
    """按标题层级组织上下文，每个 chunk 携带 title_path。

    规则：
    - 文本块归属当前标题路径；表格整块独立成 chunk
    - 累计超 chunk_size 时落块，并对超长单段递归细分
    - 过短碎块与后段合并（min_chunk_size）
    """
    units: list[tuple[list[str], Block]] = []   # (title_path, block)
    path: list[str] = []
    for block in doc.blocks:
        if block.kind == "heading":
            level = max(block.level, 1)
            path = path[: level - 1]
            path.append(block.text)
            continue
        units.append((list(path), block))

    chunks: list[Chunk] = []
    buf: list[str] = []
    buf_path: list[str] = []
    buf_page: int | None = None
    buf_type = "text"

    def flush() -> None:
        nonlocal buf, buf_path, buf_page, buf_type
        text = "\n\n".join(buf).strip()
        buf = []
        if not text:
            return
        prefix = " / ".join(buf_path)
        body = f"[{prefix}]\n{text}" if prefix else text
        if estimate_tokens(body) > chunk_size:
            for piece in recursive_split(body, chunk_size, chunk_overlap):
                chunks.append(Chunk(piece, len(chunks), list(buf_path), buf_page, buf_type))
        else:
            chunks.append(Chunk(body, len(chunks), list(buf_path), buf_page, buf_type))
        buf_page = None
        buf_type = "text"

    for title_path, block in units:
        if block.kind == "table":
            flush()
            chunks.append(Chunk(block.text, len(chunks), list(title_path), block.page, "table"))
            continue
        if buf and estimate_tokens("\n\n".join(buf + [block.text])) > chunk_size:
            flush()
        if not buf:
            buf_path = list(title_path)
            buf_page = block.page
        buf.append(block.text)
    flush()

    chunks = _merge_tiny(chunks, min_chunk_size, chunk_size)
    for i, ch in enumerate(chunks):
        ch.chunk_index = i
    return chunks


def _merge_tiny(chunks: list[Chunk], min_size: int, chunk_size: int) -> list[Chunk]:
    """过短碎块并入后块（保持顺序，表格不合并）。"""
    merged: list[Chunk] = []
    for ch in chunks:
        if (merged and ch.content_type == "text"
                and estimate_tokens(ch.content) < min_size
                and merged[-1].content_type == "text"
                and merged[-1].title_path == ch.title_path
                and estimate_tokens(merged[-1].content + ch.content) <= chunk_size):
            merged[-1].content += "\n\n" + ch.content
        else:
            merged.append(ch)
    return merged


# ------------------------------------------------------------------ 入口

def chunk_document(doc: ParserOutput, strategy: str, chunk_size: int,
                   chunk_overlap: int, min_chunk_size: int) -> list[Chunk]:
    if strategy == "recursive":
        full_text = "\n\n".join(b.text for b in doc.blocks if b.kind != "heading")
        pieces = recursive_split(full_text, chunk_size, chunk_overlap)
        return [Chunk(p, i, page=None) for i, p in enumerate(pieces)]
    return structure_chunks(doc, chunk_size, chunk_overlap, min_chunk_size)
