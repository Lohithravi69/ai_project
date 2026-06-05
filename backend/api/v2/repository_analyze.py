from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_session
from backend.services.knowledge_graph import KnowledgeGraphBuilder


router = APIRouter(prefix="/api/v2")


class AnalyzeRequest(BaseModel):
    repository_id: str
    repo_root: str | None = None


class AnalyzeResponse(BaseModel):
    nodes: int
    edges: int


@router.post("/repository/analyze", response_model=AnalyzeResponse)
async def analyze_repository(payload: AnalyzeRequest, session: AsyncSession = Depends(get_session)):
    kg = KnowledgeGraphBuilder()
    try:
        repo_root = Path(payload.repo_root) if payload.repo_root else None
        result = await kg.build_graph(session, payload.repository_id, repo_root or Path("."))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AnalyzeResponse(nodes=result.get("nodes", 0), edges=result.get("edges", 0))
