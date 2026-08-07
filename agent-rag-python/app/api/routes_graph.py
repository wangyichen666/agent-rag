"""知识图谱接口：可视化数据 + 统计。供 Java 代理给前端，内网 Token 鉴权。"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Query

from app.api.deps import AppDeps, get_deps
from app.core.security import verify_internal_token
from app.schemas import GraphData, GraphStats

router = APIRouter(dependencies=[Depends(verify_internal_token)])


@router.get("/v1/graph/{kb_id}", response_model=GraphData)
async def graph_data(kb_id: str,
                     limit: int = Query(300, ge=1, le=1000),
                     deps: AppDeps = Depends(get_deps)):
    """返回一个知识库的图谱（实体-关系-出处块），供前端可视化。"""
    if not deps.settings.graph_enabled:
        return GraphData(kb_id=kb_id, enabled=False)
    nodes, edges, truncated = await asyncio.to_thread(
        deps.graph_store.graph_data, kb_id, limit
    )
    return GraphData(kb_id=kb_id, enabled=True, nodes=nodes, edges=edges,
                     truncated=truncated)


@router.get("/v1/graph/{kb_id}/stats", response_model=GraphStats)
async def graph_stats(kb_id: str, deps: AppDeps = Depends(get_deps)):
    """图谱规模统计：实体数 / 关系数 / 出处块数。"""
    if not deps.settings.graph_enabled:
        return GraphStats(kb_id=kb_id, enabled=False)
    counts = await asyncio.to_thread(deps.graph_store.stats, kb_id)
    return GraphStats(kb_id=kb_id, enabled=True, **counts)
