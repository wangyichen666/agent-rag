"""健康检查。"""
import asyncio

from fastapi import APIRouter, Depends

from app.api.deps import AppDeps, get_deps
from app.schemas import HealthResponse

router = APIRouter()


@router.get("/healthz", response_model=HealthResponse)
async def healthz(deps: AppDeps = Depends(get_deps)):
    """各组件并行探测；模型类组件首次探测会触发加载，可能较慢。"""
    store_health, emb_health, rerank_health, graph_health, llm_health = await asyncio.gather(
        asyncio.to_thread(deps.store.health),
        asyncio.to_thread(deps.embedder.health),
        asyncio.to_thread(deps.reranker.health),
        asyncio.to_thread(deps.graph_store.health),
        deps.llm.health(),
    )
    components = {
        "vector_store": store_health,
        "embedding_model": emb_health,
        "reranker": rerank_health,
        "knowledge_graph": graph_health,
        "llm": llm_health,
    }
    ok = all(v.startswith("ok") or v == "disabled" for v in components.values())
    settings = deps.settings
    return HealthResponse(
        status="ok" if ok else "degraded",
        components=components,
        models={
            "embedding": settings.embedding_model_name,
            "reranker": settings.reranker_model_name,
            "llm": settings.llm_model,
        },
    )
