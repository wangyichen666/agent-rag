"""核心逻辑单元测试（不依赖模型与三方服务）。

运行：pytest tests/ -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.chunkers import chunk_document, estimate_tokens, recursive_split
from app.rag.embedder import FakeEmbedder
from app.rag.parsers import Block, ParserOutput, fix_broken_lines
from app.rag.retriever import rrf_fuse
from app.rag.vector_store import InMemoryStore, ScoredChunk, StoredChunk


def _sample_doc() -> ParserOutput:
    return ParserOutput(blocks=[
        Block("heading", "第一章 概述", level=1, page=1),
        Block("text", "本系统是一个企业知识库问答平台。" * 5, page=1),
        Block("heading", "1.1 架构", level=2, page=2),
        Block("text", "系统分为前端、Java 业务层、Python AI 层三部分。" * 3, page=2),
        Block("table", "| 组件 | 技术 |\n| --- | --- |\n| 前端 | React |", page=3),
    ], source_name="test.md")


def test_structure_chunks_keep_title_path_and_table():
    chunks = chunk_document(_sample_doc(), "structure", 80, 10, 5)
    assert len(chunks) >= 2
    assert chunks[0].title_path == ["第一章 概述"]
    assert any(c.content_type == "table" for c in chunks)
    assert any("1.1 架构" in c.title_path for c in chunks)


def test_recursive_split_respects_size_with_overlap():
    pieces = recursive_split("人工智能技术飞速发展。" * 200, 100, 10)
    assert len(pieces) > 3
    assert all(estimate_tokens(p) <= 220 for p in pieces)


def test_rrf_prefers_chunk_seen_in_both_channels():
    dense = [ScoredChunk("a", "d", "ca", {}, 1.0, 1),
             ScoredChunk("b", "d", "cb", {}, 0.9, 2),
             ScoredChunk("c", "d", "cc", {}, 0.8, 3)]
    sparse = [ScoredChunk("b", "d", "cb", {}, 2.0, 1),
              ScoredChunk("d", "d", "cd", {}, 1.5, 2)]
    fused = rrf_fuse(dense, sparse, 60)
    assert fused[0].chunk_id == "b"
    assert fused[0].dense_rank == 2 and fused[0].sparse_rank == 1


def test_fix_broken_lines_cjk():
    assert fix_broken_lines("这是一段被\n强行断开的文字。") == "这是一段被强行断开的文字。"


def test_memory_store_roundtrip():
    emb = FakeEmbedder()
    store = InMemoryStore()
    vec = emb.embed_texts(["vLLM 部署需要多少显存？"], False)
    store.upsert([StoredChunk("kb1", "d1", "d1-0", "vLLM 部署 14B 约需 12GB 显存。",
                              vec.dense[0], vec.sparse[0])])
    hits = store.search_dense(["kb1"], emb.embed_texts(["显存"], True).dense[0], 5)
    assert hits and hits[0].chunk_id == "d1-0"
    # 权限过滤：其他知识库查不到
    assert store.search_dense(["kb2"], emb.embed_texts(["显存"], True).dense[0], 5) == []
    store.delete_doc("kb1", "d1")
    assert store.search_dense(["kb1"], emb.embed_texts(["显存"], True).dense[0], 5) == []
