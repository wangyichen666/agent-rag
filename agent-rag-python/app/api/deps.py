"""依赖容器：模型与存储均为进程级单例，首次使用时初始化。"""
from dataclasses import dataclass

from fastapi import Request

from app.core.config import Settings, get_settings
from app.rag.embedder import build_embedder
from app.rag.generator import LlmClient
from app.rag.graph_store import GraphStore, build_graph_store
from app.rag.reranker import build_reranker
from app.rag.vector_store import VectorStore, build_store


@dataclass
class AppDeps:
    settings: Settings
    embedder: object
    reranker: object
    store: VectorStore
    graph_store: GraphStore
    llm: LlmClient


def build_deps() -> AppDeps:
    settings = get_settings()
    return AppDeps(
        settings=settings,
        embedder=build_embedder(settings),
        reranker=build_reranker(settings),
        store=build_store(settings),
        graph_store=build_graph_store(settings),
        llm=LlmClient(settings),
    )


def get_deps(request: Request) -> AppDeps:
    return request.app.state.deps
