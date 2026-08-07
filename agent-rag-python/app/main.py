"""agent-rag-python 入口：FastAPI 应用装配。"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.deps import build_deps
from app.api.routes_chat import router as chat_router
from app.api.routes_debug import router as debug_router
from app.api.routes_graph import router as graph_router
from app.api.routes_ingest import router as ingest_router
from app.api.routes_misc import router as misc_router
from app.core.config import get_settings
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    logger.info("starting %s, vector_store=%s, embedding_enabled=%s, reranker_enabled=%s",
                settings.app_name, settings.vector_store,
                settings.embedding_enabled, settings.reranker_enabled)
    app.state.deps = build_deps()
    yield
    await app.state.deps.llm.close()
    app.state.deps.graph_store.close()


app = FastAPI(title="agent-rag-python", version="0.1.0", lifespan=lifespan)

app.include_router(chat_router)
app.include_router(debug_router)
app.include_router(graph_router)
app.include_router(ingest_router)
app.include_router(misc_router)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={
        "code": "INVALID_REQUEST", "message": str(exc.errors()[:3]),
    })


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    logger.exception("unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={
        "code": "INTERNAL_ERROR", "message": str(exc),
    })


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)
