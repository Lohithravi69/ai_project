from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_session


router = APIRouter(prefix="/api/v2")


class GraphRequest(BaseModel):
    repository_id: str
    limit: int | None = 1000


class Node(BaseModel):
    node_id: str
    node_type: str
    name: str
    canonical_path: str | None = None
    metadata_json: dict = {}


class Edge(BaseModel):
    edge_id: str
    from_node: str
    to_node: str
    edge_type: str
    metadata_json: dict = {}


class GraphResponse(BaseModel):
    nodes: List[Node]
    edges: List[Edge]


@router.post("/repository/graph", response_model=GraphResponse)
async def get_repository_graph(payload: GraphRequest, session: AsyncSession = Depends(get_session)):
    try:
        nodes_q = text(
            "SELECT node_id, node_type, name, canonical_path, metadata_json FROM project_graph_nodes WHERE repository_id = :rid LIMIT :limit"
        )
        edges_q = text(
            "SELECT edge_id, from_node, to_node, edge_type, metadata_json FROM project_graph_edges WHERE repository_id = :rid LIMIT :limit"
        )
        nodes_res = await session.execute(nodes_q, {"rid": payload.repository_id, "limit": payload.limit or 1000})
        edges_res = await session.execute(edges_q, {"rid": payload.repository_id, "limit": payload.limit or 1000})
        nodes = [dict(row) for row in nodes_res.mappings().all()]
        edges = [dict(row) for row in edges_res.mappings().all()]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return GraphResponse(nodes=nodes, edges=edges)
