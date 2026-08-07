"""知识图谱核心逻辑单元测试（不依赖 Neo4j / 外部 LLM）。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.rag.extractor import extract_query_entities, extract_triples_batch, parse_json_array
from app.rag.graph_retriever import GraphCandidate, graph_retrieve
from app.rag.graph_store import DisabledGraphStore, GraphHit
from app.rag.retriever import Candidate, fuse_graph


class FakeLlm:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def chat_once(self, messages, model=None, temperature=0.0, max_tokens=256):
        self.calls += 1
        return self._responses.pop(0) if self._responses else "[]"


def test_parse_json_array_tolerates_fences_and_garbage():
    assert parse_json_array('```json\n[{"a":1}]\n```') == [{"a": 1}]
    assert parse_json_array("说明：结果是\n[1, 2, 3]\n完毕") == [1, 2, 3]
    assert parse_json_array("没有数组") == []
    assert parse_json_array("") == []


def test_extract_triples_batch_maps_chunk_index():
    settings = get_settings()
    llm = FakeLlm([(
        '[{"chunk_index":1,"head":"Milvus","relation":"属于","tail":"向量库",'
        '"head_type":"系统","tail_type":"概念"},'
        '{"chunk_index":2,"head":"Java","relation":"依赖","tail":"Python",'
        '"head_type":"系统","tail_type":"系统"}]'
    )])
    items = [("c1", "Milvus 是向量库。"), ("c2", "Java 依赖 Python。")]
    triples = asyncio.run(extract_triples_batch(llm, items, settings))
    assert llm.calls == 1
    assert len(triples["c1"]) == 1
    assert triples["c1"][0].relation == "属于"
    assert len(triples["c2"]) == 1
    assert triples["c2"][0].head == "Java"


def test_extract_batch_skips_bad_json_without_raising():
    settings = get_settings()
    llm = FakeLlm(["这不是 JSON", '[]'])
    triples = asyncio.run(extract_triples_batch(llm, [("c1", "文本")], settings))
    assert triples == {}


def test_extract_query_entities_falls_back_on_bad_output():
    settings = get_settings()
    llm = FakeLlm(["抱歉，我无法回答"])
    assert asyncio.run(extract_query_entities(llm, "Milvus 的维度是多少？", settings)) == []
    llm2 = FakeLlm(['["Milvus", "HNSW"]'])
    assert asyncio.run(extract_query_entities(llm2, "Milvus 的 HNSW 参数？", settings)) == ["Milvus", "HNSW"]


def test_fuse_graph_merges_and_reranks():
    base = [
        Candidate("a", "d1", "ca", {}, dense_rank=1, rrf_score=1 / 61),
        Candidate("b", "d1", "cb", {}, dense_rank=2, rrf_score=1 / 62),
    ]
    graph = [
        GraphCandidate("b", "d1", "cb", {}, hop=1, score=0.9),
        GraphCandidate("c", "d2", "cc", {}, hop=2, score=0.5),
    ]
    fused = fuse_graph(base, graph, 60)
    assert fused[0].chunk_id == "b"  # 双通道命中排最前
    by_id = {c.chunk_id: c for c in fused}
    assert by_id["b"].graph_rank == 1
    assert by_id["c"].graph_rank == 2
    assert by_id["c"].graph_hops == 2


def test_graph_retrieve_degrades_when_disabled_or_empty():
    settings = get_settings()
    store = DisabledGraphStore()
    llm = FakeLlm(["[]"])
    result = asyncio.run(graph_retrieve(store, llm, ["kb1"], "问题", settings))
    assert result == []

    class EmptyStore(DisabledGraphStore):
        def fallback_match_entities(self, kb_ids, query, limit=10):
            return []

    result2 = asyncio.run(graph_retrieve(EmptyStore(), llm, ["kb1"], "问题", settings))
    assert result2 == []


def test_graph_hit_shapes():
    h = GraphHit("c1", "d1", "content", {"source_file": "a.md"}, hop=1, score=0.5)
    assert h.metadata["source_file"] == "a.md"
