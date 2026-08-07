"""知识图谱存储：Neo4j 实现（仅需 neo4j 驱动，无额外服务）。

数据模型（按 kb_id 分区，一个知识库一张子图）：
    (:Entity {kb_id, name, name_lower, entity_type})
    (:Chunk  {kb_id, doc_id, chunk_id, content, source_file, page, title_path})
    (e1)-[:RELATES_TO  {kb_id, relation, doc_id}]->(e2)   # 抽取出的关系
    (e)-[:MENTIONED_IN {kb_id, doc_id}]->(c)              # 实体出处块

图谱构建/检索均独立于向量库：Neo4j 不可用时所有调用降级为空，不阻塞主流程。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class ChunkRef:
    """图谱要登记的文档块（内容 + 展示元数据）。"""
    chunk_id: str
    content: str
    metadata: dict = field(default_factory=dict)


@dataclass
class GraphHit:
    """图检索命中的文档块。hop 为从问题实体出发的最短路径长度。"""
    chunk_id: str
    doc_id: str
    content: str
    metadata: dict = field(default_factory=dict)
    hop: int = 1
    score: float = 0.0


class GraphStore(ABC):
    @abstractmethod
    def upsert_doc(self, kb_id: str, doc_id: str, chunks: list[ChunkRef],
                   triples_by_chunk: dict[str, list]) -> None: ...

    @abstractmethod
    def delete_doc(self, kb_id: str, doc_id: str) -> None: ...

    @abstractmethod
    def delete_kb(self, kb_id: str) -> None: ...

    @abstractmethod
    def match_entities(self, kb_ids: list[str], names: list[str]) -> list[str]: ...

    @abstractmethod
    def fallback_match_entities(self, kb_ids: list[str], query: str, limit: int = 10) -> list[str]: ...

    @abstractmethod
    def search(self, kb_ids: list[str], names: list[str], max_hops: int,
               top_k: int) -> list[GraphHit]: ...

    @abstractmethod
    def graph_data(self, kb_id: str, limit: int) -> tuple[list[dict], list[dict], bool]: ...

    @abstractmethod
    def stats(self, kb_id: str) -> dict[str, int]: ...

    @abstractmethod
    def health(self) -> str: ...

    @abstractmethod
    def close(self) -> None: ...


class DisabledGraphStore(GraphStore):
    """graph_enabled=False 时的空实现，所有方法安全降级。"""

    def upsert_doc(self, kb_id: str, doc_id: str, chunks: list[ChunkRef],
                   triples_by_chunk: dict[str, list]) -> None:
        return None

    def delete_doc(self, kb_id: str, doc_id: str) -> None:
        return None

    def delete_kb(self, kb_id: str) -> None:
        return None

    def match_entities(self, kb_ids: list[str], names: list[str]) -> list[str]:
        return []

    def fallback_match_entities(self, kb_ids: list[str], query: str, limit: int = 10) -> list[str]:
        return []

    def search(self, kb_ids: list[str], names: list[str], max_hops: int,
               top_k: int) -> list[GraphHit]:
        return []

    def graph_data(self, kb_id: str, limit: int) -> tuple[list[dict], list[dict], bool]:
        return [], [], False

    def stats(self, kb_id: str) -> dict[str, int]:
        return {"entity_count": 0, "relation_count": 0, "chunk_count": 0}

    def health(self) -> str:
        return "disabled"

    def close(self) -> None:
        return None


class Neo4jGraphStore(GraphStore):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._driver = None

    # ------------------------------------------------------------- 连接

    def _connect(self):
        if self._driver is not None:
            return self._driver
        from neo4j import GraphDatabase  # 延迟导入，避免启动时强制依赖

        logger.info("connecting neo4j %s", self._settings.neo4j_uri)
        self._driver = GraphDatabase.driver(
            self._settings.neo4j_uri,
            auth=(self._settings.neo4j_user, self._settings.neo4j_password),
            connection_timeout=5,
        )
        self._ensure_schema()
        return self._driver

    def _ensure_schema(self) -> None:
        with self._driver.session() as session:
            session.run(
                "CREATE CONSTRAINT entity_unique IF NOT EXISTS "
                "FOR (e:Entity) REQUIRE (e.kb_id, e.name) IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT chunk_unique IF NOT EXISTS "
                "FOR (c:Chunk) REQUIRE (c.kb_id, c.chunk_id) IS UNIQUE"
            )

    def _run(self, query: str, **params) -> list[dict]:
        driver = self._connect()
        with driver.session() as session:
            return [dict(rec) for rec in session.run(query, **params)]

    # ------------------------------------------------------------- 写入

    def upsert_doc(self, kb_id: str, doc_id: str, chunks: list[ChunkRef],
                   triples_by_chunk: dict[str, list]) -> None:
        if not chunks:
            return
        self.delete_doc(kb_id, doc_id)  # 幂等：先清旧图

        chunk_rows = [
            {
                "kb_id": kb_id, "doc_id": doc_id, "chunk_id": c.chunk_id,
                "content": c.content[:8000],
                "source_file": c.metadata.get("source_file", ""),
                "page": c.metadata.get("page"),
                "title_path": c.metadata.get("title_path") or [],
            }
            for c in chunks
        ]
        triple_rows: list[dict] = []
        mention_rows: list[dict] = []
        for c in chunks:
            for t in triples_by_chunk.get(c.chunk_id, []):
                triple_rows.append({
                    "kb_id": kb_id, "doc_id": doc_id, "chunk_id": c.chunk_id,
                    "head": t.head, "relation": t.relation, "tail": t.tail,
                    "head_type": t.head_type, "tail_type": t.tail_type,
                })
                mention_rows.append({"kb_id": kb_id, "doc_id": doc_id,
                                     "chunk_id": c.chunk_id, "entity": t.head})
                mention_rows.append({"kb_id": kb_id, "doc_id": doc_id,
                                     "chunk_id": c.chunk_id, "entity": t.tail})

        with self._connect().session() as session:
            # 1. Chunk 节点（MERGE 幂等）
            if chunk_rows:
                session.run(
                    "UNWIND $rows AS r "
                    "MERGE (c:Chunk {kb_id: r.kb_id, chunk_id: r.chunk_id}) "
                    "SET c.doc_id = r.doc_id, c.content = r.content, "
                    "c.source_file = r.source_file, c.page = r.page, "
                    "c.title_path = r.title_path",
                    rows=chunk_rows,
                )
            # 2. 实体节点 + 关系边（同文档同关系去重）
            if triple_rows:
                session.run(
                    "UNWIND $rows AS t "
                    "MERGE (h:Entity {kb_id: t.kb_id, name: t.head}) "
                    "SET h.name_lower = toLower(t.head), "
                    "h.entity_type = CASE WHEN t.head_type <> '' THEN t.head_type ELSE h.entity_type END "
                    "MERGE (a:Entity {kb_id: t.kb_id, name: t.tail}) "
                    "SET a.name_lower = toLower(t.tail), "
                    "a.entity_type = CASE WHEN t.tail_type <> '' THEN t.tail_type ELSE a.entity_type END "
                    "MERGE (h)-[r:RELATES_TO {kb_id: t.kb_id, relation: t.relation, doc_id: t.doc_id}]->(a) "
                    "SET r.chunk_id = t.chunk_id",
                    rows=triple_rows,
                )
            # 3. 实体 → 出处块
            if mention_rows:
                session.run(
                    "UNWIND $rows AS m "
                    "MATCH (e:Entity {kb_id: m.kb_id, name: m.entity}) "
                    "MATCH (c:Chunk {kb_id: m.kb_id, chunk_id: m.chunk_id}) "
                    "MERGE (e)-[r:MENTIONED_IN {kb_id: m.kb_id, doc_id: m.doc_id}]->(c)",
                    rows=mention_rows,
                )
        logger.info("graph upsert kb=%s doc=%s chunks=%d triples=%d",
                    kb_id, doc_id, len(chunks), len(triple_rows))

    def delete_doc(self, kb_id: str, doc_id: str) -> None:
        try:
            with self._connect().session() as session:
                session.run(
                    "MATCH (e1:Entity {kb_id: $kb_id})-[r:RELATES_TO {kb_id: $kb_id, doc_id: $doc_id}]->(:Entity {kb_id: $kb_id}) "
                    "DELETE r",
                    kb_id=kb_id, doc_id=doc_id,
                )
                session.run(
                    "MATCH (c:Chunk {kb_id: $kb_id, doc_id: $doc_id}) DETACH DELETE c",
                    kb_id=kb_id, doc_id=doc_id,
                )
                # 清理没有任何连边的孤立实体
                session.run(
                    "MATCH (e:Entity {kb_id: $kb_id}) WHERE NOT (e)--() DELETE e",
                    kb_id=kb_id,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("graph delete_doc failed kb=%s doc=%s: %s", kb_id, doc_id, exc)

    def delete_kb(self, kb_id: str) -> None:
        try:
            with self._connect().session() as session:
                session.run("MATCH (n {kb_id: $kb_id}) DETACH DELETE n", kb_id=kb_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("graph delete_kb failed kb=%s: %s", kb_id, exc)

    # ------------------------------------------------------------- 检索

    def match_entities(self, kb_ids: list[str], names: list[str]) -> list[str]:
        if not names:
            return []
        rows = self._run(
            "MATCH (e:Entity) WHERE e.kb_id IN $kb_ids AND e.name IN $names "
            "RETURN e.name AS name",
            kb_ids=kb_ids, names=names,
        )
        return [r["name"] for r in rows]

    def fallback_match_entities(self, kb_ids: list[str], query: str, limit: int = 10) -> list[str]:
        rows = self._run(
            "MATCH (e:Entity) WHERE e.kb_id IN $kb_ids AND toLower($text) CONTAINS e.name_lower "
            "RETURN e.name AS name LIMIT $limit",
            kb_ids=kb_ids, text=query, limit=limit,
        )
        return [r["name"] for r in rows]

    def search(self, kb_ids: list[str], names: list[str], max_hops: int,
               top_k: int) -> list[GraphHit]:
        if not names:
            return []
        hops = max(1, min(int(max_hops), 5))
        rows = self._run(
            "MATCH (e:Entity) WHERE e.kb_id IN $kb_ids AND e.name IN $names "
            f"MATCH path = (e)-[:RELATES_TO|MENTIONED_IN*1..{hops}]-(c:Chunk) "
            "WHERE c.kb_id IN $kb_ids "
            "WITH c, min(length(path)) AS hop, count(*) AS hits "
            "RETURN c.chunk_id AS chunk_id, c.doc_id AS doc_id, c.content AS content, "
            "c.source_file AS source_file, c.page AS page, c.title_path AS title_path, "
            "hop, hits "
            "ORDER BY hop ASC, hits DESC LIMIT $top_k",
            kb_ids=kb_ids, names=names, top_k=top_k,
        )
        hits: list[GraphHit] = []
        for r in rows:
            hop = int(r["hop"])
            score = (1.0 / (hop + 1)) * (1.0 + min(int(r["hits"]), 10) * 0.1)
            hits.append(GraphHit(
                chunk_id=r["chunk_id"], doc_id=r["doc_id"], content=r["content"],
                metadata={
                    "source_file": r["source_file"] or "",
                    "page": r["page"],
                    "title_path": r["title_path"] or [],
                },
                hop=hop, score=round(score, 4),
            ))
        return hits

    # ------------------------------------------------------------- 可视化

    def graph_data(self, kb_id: str, limit: int) -> tuple[list[dict], list[dict], bool]:
        node_limit = max(1, min(int(limit), 1000))
        edge_limit = node_limit * 3
        try:
            entity_rows = self._run(
                "MATCH (e:Entity {kb_id: $kb_id}) WHERE (e)--() "
                "RETURN e.name AS name, e.entity_type AS entity_type "
                "LIMIT $limit",
                kb_id=kb_id, limit=node_limit,
            )
            rel_rows = self._run(
                "MATCH (a:Entity {kb_id: $kb_id})-[r:RELATES_TO {kb_id: $kb_id}]->(b:Entity {kb_id: $kb_id}) "
                "RETURN a.name AS head, b.name AS tail, r.relation AS relation "
                "LIMIT $limit",
                kb_id=kb_id, limit=edge_limit,
            )
            chunk_rows = self._run(
                "MATCH (e:Entity {kb_id: $kb_id})-[:MENTIONED_IN {kb_id: $kb_id}]->(c:Chunk {kb_id: $kb_id}) "
                "RETURN e.name AS entity, c.chunk_id AS chunk_id, c.doc_id AS doc_id, "
                "c.source_file AS source_file "
                "LIMIT $limit",
                kb_id=kb_id, limit=edge_limit,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("graph_data failed kb=%s: %s", kb_id, exc)
            return [], [], False

        nodes: dict[str, dict] = {}
        edges: list[dict] = []

        for r in entity_rows:
            nodes[f"e:{r['name']}"] = {
                "id": f"e:{r['name']}", "label": r["name"], "kind": "entity",
                "entity_type": r.get("entity_type") or "",
            }
        for r in rel_rows:
            head_id = f"e:{r['head']}"
            tail_id = f"e:{r['tail']}"
            nodes.setdefault(head_id, {"id": head_id, "label": r["head"], "kind": "entity", "entity_type": ""})
            nodes.setdefault(tail_id, {"id": tail_id, "label": r["tail"], "kind": "entity", "entity_type": ""})
            edges.append({"source": head_id, "target": tail_id,
                          "label": r.get("relation") or "", "kind": "relates"})
        for r in chunk_rows:
            chunk_id = f"c:{r['chunk_id']}"
            nodes.setdefault(chunk_id, {
                "id": chunk_id, "label": r["chunk_id"][-24:], "kind": "chunk",
                "entity_type": "", "doc_id": r.get("doc_id") or "",
                "source_file": r.get("source_file") or "",
            })
            edges.append({"source": f"e:{r['entity']}", "target": chunk_id,
                          "label": "", "kind": "mentioned"})

        truncated = (len(entity_rows) >= node_limit or len(rel_rows) >= edge_limit
                     or len(chunk_rows) >= edge_limit)
        return list(nodes.values()), edges, truncated

    def stats(self, kb_id: str) -> dict[str, int]:
        try:
            e = self._run("MATCH (e:Entity {kb_id: $kb_id}) RETURN count(e) AS n", kb_id=kb_id)
            r = self._run(
                "MATCH (:Entity {kb_id: $kb_id})-[r:RELATES_TO {kb_id: $kb_id}]->(:Entity {kb_id: $kb_id}) "
                "RETURN count(r) AS n",
                kb_id=kb_id,
            )
            c = self._run("MATCH (c:Chunk {kb_id: $kb_id}) RETURN count(c) AS n", kb_id=kb_id)
            return {
                "entity_count": int(e[0]["n"]) if e else 0,
                "relation_count": int(r[0]["n"]) if r else 0,
                "chunk_count": int(c[0]["n"]) if c else 0,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("graph stats failed kb=%s: %s", kb_id, exc)
            return {"entity_count": 0, "relation_count": 0, "chunk_count": 0}

    def health(self) -> str:
        try:
            self._connect()
            return "ok"
        except Exception as exc:  # noqa: BLE001
            return f"error: {exc}"

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None


def build_graph_store(settings: Settings) -> GraphStore:
    if not settings.graph_enabled:
        logger.info("knowledge graph disabled")
        return DisabledGraphStore()
    return Neo4jGraphStore(settings)
