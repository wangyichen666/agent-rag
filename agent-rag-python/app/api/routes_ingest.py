"""文档入库路由：异步任务 + 状态查询。"""
import asyncio

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import AppDeps, get_deps
from app.core.security import verify_internal_token
from app.schemas import (DeleteDocumentRequest, IngestAccepted, IngestRequest,
                         IngestStatus, KbCreateRequest, KbDeleteRequest,
                         OkResponse)
from app.services.ingest_service import registry, run_ingest

router = APIRouter(dependencies=[Depends(verify_internal_token)])


@router.post("/v1/ingest", response_model=IngestAccepted,
             status_code=status.HTTP_202_ACCEPTED)
async def ingest(req: IngestRequest, deps: AppDeps = Depends(get_deps)):
    task_id = registry.create(req.doc_id)
    asyncio.create_task(run_ingest(req, deps))
    return IngestAccepted(doc_id=req.doc_id, task_id=task_id)


@router.get("/v1/ingest/status/{task_id}", response_model=IngestStatus)
async def ingest_status(task_id: str):
    task = registry.get(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "TASK_NOT_FOUND", "message": task_id})
    return task


@router.post("/v1/documents/delete", response_model=OkResponse)
async def delete_document(req: DeleteDocumentRequest, deps: AppDeps = Depends(get_deps)):
    deps.store.delete_doc(req.kb_id, req.doc_id)
    deps.graph_store.delete_doc(req.kb_id, req.doc_id)
    return OkResponse()


@router.post("/v1/kb/create", response_model=OkResponse)
async def kb_create(req: KbCreateRequest, deps: AppDeps = Depends(get_deps)):
    # collection 按 partition key 自动隔离，无需显式建分区；接口保留以固定契约
    return OkResponse()


@router.post("/v1/kb/delete", response_model=OkResponse)
async def kb_delete(req: KbDeleteRequest, deps: AppDeps = Depends(get_deps)):
    deps.store.delete_kb(req.kb_id)
    deps.graph_store.delete_kb(req.kb_id)
    return OkResponse()
