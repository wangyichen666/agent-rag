"""API 契约模型，与《03-服务接口设计》严格对齐。改动需同步 Java 侧。"""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ---------- 通用 ----------

class ErrorBody(BaseModel):
    code: str
    message: str


# ---------- chat ----------

class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatOptions(BaseModel):
    stream: bool = True
    rewrite_query: bool = True
    dense_top_k: Optional[int] = None
    sparse_top_k: Optional[int] = None
    rerank_top_n: Optional[int] = None
    score_threshold: Optional[float] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class ChatRequest(BaseModel):
    session_id: str
    trace_id: str = ""
    kb_ids: list[str]
    question: str
    history: list[HistoryMessage] = Field(default_factory=list)
    options: ChatOptions = Field(default_factory=ChatOptions)


class Citation(BaseModel):
    ref_id: int
    chunk_id: str
    doc_id: str
    source_file: str = ""
    page: Optional[int] = None
    title_path: list[str] = Field(default_factory=list)
    score: float = 0.0


class RetrievalDebug(BaseModel):
    rewritten_query: str = ""
    dense_hits: int = 0
    sparse_hits: int = 0
    graph_hits: int = 0
    rerank_scores: list[float] = Field(default_factory=list)
    trace_id: str = ""


# ---------- retrieve ----------

class RetrieveRequest(BaseModel):
    kb_ids: list[str]
    query: str
    dense_top_k: Optional[int] = None
    sparse_top_k: Optional[int] = None
    rerank_top_n: Optional[int] = None


class RetrieveResultItem(BaseModel):
    chunk_id: str
    content: str
    rerank_score: float
    dense_rank: Optional[int] = None
    sparse_rank: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrieveResponse(BaseModel):
    results: list[RetrieveResultItem]


# ---------- ingest ----------

class IngestFile(BaseModel):
    url: str
    name: str
    type: str


class ChunkConfig(BaseModel):
    strategy: Literal["structure", "recursive"] = "structure"
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    parent_child: bool = False


class IngestRequest(BaseModel):
    kb_id: str
    doc_id: str
    file: IngestFile
    parser: Literal["fast", "quality"] = "fast"
    chunk_config: ChunkConfig = Field(default_factory=ChunkConfig)
    callback_url: Optional[str] = None


class IngestAccepted(BaseModel):
    doc_id: str
    task_id: str
    status: str = "processing"


class IngestCallback(BaseModel):
    doc_id: str
    status: Literal["success", "failed"]
    chunk_count: int = 0
    elapsed_ms: int = 0
    error: Optional[str] = None


class IngestStatus(BaseModel):
    task_id: str
    doc_id: str
    status: Literal["processing", "success", "failed"]
    chunk_count: int = 0
    error: Optional[str] = None


# ---------- documents / kb ----------

class DeleteDocumentRequest(BaseModel):
    kb_id: str
    doc_id: str


class KbCreateRequest(BaseModel):
    kb_id: str


class KbDeleteRequest(BaseModel):
    kb_id: str


class KbRebuildRequest(BaseModel):
    kb_id: str


class OkResponse(BaseModel):
    ok: bool = True


# ---------- healthz ----------

class HealthResponse(BaseModel):
    status: str
    components: dict[str, str]
    models: dict[str, str]


# ---------- knowledge graph ----------

class GraphNode(BaseModel):
    id: str
    label: str
    kind: Literal["entity", "chunk"]
    entity_type: str = ""
    doc_id: str = ""
    source_file: str = ""


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str = ""
    kind: Literal["relates", "mentioned"]


class GraphData(BaseModel):
    kb_id: str
    enabled: bool = True
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    truncated: bool = False


class GraphStats(BaseModel):
    kb_id: str
    enabled: bool = True
    entity_count: int = 0
    relation_count: int = 0
    chunk_count: int = 0
