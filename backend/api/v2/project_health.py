from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_session
from backend.services.project_health import ProjectHealth


router = APIRouter(prefix="/api/v2")


class HealthRequest(BaseModel):
    repository_id: str
    repo_root: str | None = None


class HealthResponse(BaseModel):
    report: dict


@router.post("/project/health", response_model=HealthResponse)
async def project_health(payload: HealthRequest, session: AsyncSession = Depends(get_session)):
    service = ProjectHealth()
    try:
        repo_root = Path(payload.repo_root) if payload.repo_root else None
        report = await service.analyze(session, payload.repository_id, repo_root)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return HealthResponse(report=report)
