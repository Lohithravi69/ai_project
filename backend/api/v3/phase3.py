from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_session
from backend.models.schemas import (
    ActionPlanCreateRequest,
    ActionPlanRead,
    CheckpointRead,
    PlanApprovalRequest,
    RollbackCommitInput,
    RollbackResponse,
    ToolInvocationRequest,
    ToolInvocationResponse,
    ToolSpecRead,
)
from backend.services.phase3_service import Phase3Service

router = APIRouter(prefix="/api/v3", tags=["phase3"])


@router.get("/tools", response_model=list[ToolSpecRead])
async def list_tools(session: AsyncSession = Depends(get_session)):
    service = Phase3Service(session)
    return service.list_tools()


@router.post("/plans", response_model=ActionPlanRead)
async def create_plan(payload: ActionPlanCreateRequest, session: AsyncSession = Depends(get_session)):
    service = Phase3Service(session)
    return await service.create_plan(payload)


@router.get("/plans/{plan_id}", response_model=ActionPlanRead)
async def get_plan(plan_id: str, session: AsyncSession = Depends(get_session)):
    service = Phase3Service(session)
    try:
        return await service.get_plan(plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/plans/{plan_id}/approve", response_model=ActionPlanRead)
async def approve_plan(plan_id: str, payload: PlanApprovalRequest, session: AsyncSession = Depends(get_session)):
    service = Phase3Service(session)
    try:
        return await service.approve_plan(plan_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tools/invoke", response_model=ToolInvocationResponse)
async def invoke_tool(payload: ToolInvocationRequest, session: AsyncSession = Depends(get_session)):
    service = Phase3Service(session)
    try:
        return await service.invoke_tool(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/checkpoints", response_model=list[CheckpointRead])
async def list_checkpoints(repository_id: str | None = None, session: AsyncSession = Depends(get_session)):
    service = Phase3Service(session)
    return await service.list_checkpoints(repository_id=repository_id)


@router.post("/checkpoints/{checkpoint_id}/rollback", response_model=RollbackResponse)
async def rollback_checkpoint(
    checkpoint_id: str,
    dry_run: bool = Body(default=False),
    session: AsyncSession = Depends(get_session),
):
    service = Phase3Service(session)
    try:
        return await service.rollback_checkpoint(RollbackCommitInput(checkpoint_id=checkpoint_id, dry_run=dry_run))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
