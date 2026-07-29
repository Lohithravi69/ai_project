from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.approval.approval_system import ApprovalSystem
from backend.database.models import ExecutionLogRecord, RollbackHistoryRecord, ToolExecutionRecord
from backend.database.session import get_session
from backend.execution.checkpoint_engine import CheckpointEngine
from backend.execution.execution_manager import ExecutionManager
from backend.execution.rollback_engine import RollbackEngine
from backend.execution.workspace import WorkspaceManager
from backend.models.schemas import (
    ApprovalAction,
    ApprovalRequestRead,
    CheckpointReadV2,
    ExecutionLogRead,
    ExecutionPlanCreate,
    ExecutionPlanRead,
    RollbackRequestV2,
    RollbackResponseV2,
    ToolDefinition,
    ToolRunRequest,
    ToolRunResponse,
    WorkspaceRead,
)
from backend.planner.action_planner import ActionPlanner
from backend.tool_registry.registry import ToolRegistry

router = APIRouter(prefix="/api/v4", tags=["phase3-full"])


@router.get("/tools", response_model=list[ToolDefinition])
async def list_tools():
    registry = ToolRegistry()
    return [
        ToolDefinition(
            name=s.name,
            description=s.description,
            version=s.version,
            permission_level=s.permission_level,
            timeout_seconds=s.timeout_seconds,
            rollback_support=s.rollback_support,
            dry_run_support=s.dry_run_support,
            input_schema=s.input_schema_json,
            output_schema=s.output_schema_json,
        )
        for s in registry.list_tools()
    ]


@router.post("/plan", response_model=ExecutionPlanRead)
async def create_plan(payload: ExecutionPlanCreate, session: AsyncSession = Depends(get_session)):
    planner = ActionPlanner(session)
    return await planner.create_plan(payload)


@router.get("/plan/{plan_id}", response_model=ExecutionPlanRead)
async def get_plan(plan_id: str, session: AsyncSession = Depends(get_session)):
    planner = ActionPlanner(session)
    plan = await planner.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.get("/plans", response_model=list[ExecutionPlanRead])
async def list_plans(limit: int = Query(default=50, le=200), session: AsyncSession = Depends(get_session)):
    planner = ActionPlanner(session)
    return await planner.list_plans(limit=limit)


@router.post("/tools/dry-run", response_model=ToolRunResponse)
async def dry_run_tool(payload: ToolRunRequest, session: AsyncSession = Depends(get_session)):
    payload.dry_run = True
    manager = ExecutionManager(session)
    return await manager.run_tool(payload)


@router.post("/tools/run", response_model=ToolRunResponse)
async def run_tool(payload: ToolRunRequest, session: AsyncSession = Depends(get_session)):
    if payload.dry_run:
        payload.dry_run = False
    manager = ExecutionManager(session)
    return await manager.run_tool(payload)


@router.get("/approval", response_model=list[ApprovalRequestRead])
async def list_approval_requests(
    plan_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
):
    system = ApprovalSystem(session)
    return await system.list_approval_requests(plan_id=plan_id, status=status, limit=limit)


@router.get("/approval/{approval_id}", response_model=ApprovalRequestRead)
async def get_approval_request(approval_id: str, session: AsyncSession = Depends(get_session)):
    system = ApprovalSystem(session)
    request = await system.get_approval_request(approval_id)
    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return request


@router.post("/approval/approve", response_model=ApprovalRequestRead)
async def approve_request(payload: ApprovalAction = Body(...), approval_id: str = Query(...), session: AsyncSession = Depends(get_session)):
    system = ApprovalSystem(session)
    try:
        return await system.approve(approval_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/approval/reject", response_model=ApprovalRequestRead)
async def reject_request(approval_id: str = Query(...), reason: str = Body(default=""), reviewer: str = Body(default=""), session: AsyncSession = Depends(get_session)):
    system = ApprovalSystem(session)
    try:
        return await system.reject(approval_id, reason=reason, reviewer=reviewer)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/workspaces", response_model=list[WorkspaceRead])
async def list_workspaces(
    repository_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
):
    mgr = WorkspaceManager(session)
    workspaces = await mgr.list_workspaces(repository_id=repository_id, status=status, limit=limit)
    return [
        WorkspaceRead(
            id=w.id,
            plan_id=w.plan_id,
            repository_id=w.repository_id,
            repository_full_name=w.repository_full_name,
            workspace_path=w.workspace_path,
            branch_name=w.branch_name,
            base_branch=w.base_branch,
            status=w.status,
            commit_sha=w.commit_sha,
            metadata=w.metadata_json,
            created_at=w.created_at,
            updated_at=w.updated_at,
            execution_id=w.execution_id,
        )
        for w in workspaces
    ]


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceRead)
async def get_workspace(workspace_id: str, session: AsyncSession = Depends(get_session)):
    mgr = WorkspaceManager(session)
    ws = await mgr.get_workspace(workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceRead(
        id=ws.id,
        plan_id=ws.plan_id,
        repository_id=ws.repository_id,
        repository_full_name=ws.repository_full_name,
        workspace_path=ws.workspace_path,
        branch_name=ws.branch_name,
        base_branch=ws.base_branch,
        status=ws.status,
        commit_sha=ws.commit_sha,
        metadata=ws.metadata_json,
        created_at=ws.created_at,
        updated_at=ws.updated_at,
        execution_id=ws.execution_id,
    )


@router.get("/checkpoints", response_model=list[CheckpointReadV2])
async def list_checkpoints(
    plan_id: str | None = Query(default=None),
    workspace_id: str | None = Query(default=None),
    repository_id: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
):
    engine = CheckpointEngine(session)
    checkpoints = await engine.list_checkpoints(plan_id=plan_id, workspace_id=workspace_id, repository_id=repository_id, limit=limit)
    return [
        CheckpointReadV2(
            id=c.id,
            plan_id=c.plan_id,
            workspace_id=c.workspace_id,
            repository_id=c.repository_id,
            branch_name=c.branch_name,
            git_sha=c.git_sha,
            tool_name=c.tool_name,
            modified_files=c.modified_files_json,
            reasoning=c.reasoning,
            plan=c.plan_json,
            metadata=c.metadata_json,
            created_at=c.created_at,
            execution_id=c.execution_id,
        )
        for c in checkpoints
    ]


@router.post("/rollback", response_model=RollbackResponseV2)
async def rollback_checkpoint(payload: RollbackRequestV2, session: AsyncSession = Depends(get_session)):
    engine = RollbackEngine(session)
    execution_id = str(uuid4())
    try:
        result = await engine.rollback(payload.checkpoint_id, rollback_types=payload.rollback_types, dry_run=payload.dry_run, execution_id=execution_id)
        return RollbackResponseV2(
            checkpoint_id=result.checkpoint_id,
            success=result.success,
            dry_run=result.dry_run,
            summary=result.summary,
            restored_branch=result.restored_branch,
            restored_git_sha=result.restored_git_sha,
            rollback_results=result.rollback_results,
            execution_ms=result.execution_ms,
            exception_message=result.exception_message,
            execution_id=execution_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/execution/logs", response_model=list[ExecutionLogRead])
async def list_execution_logs(
    plan_id: str | None = Query(default=None),
    level: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    session: AsyncSession = Depends(get_session),
):
    from sqlalchemy import select

    query = select(ExecutionLogRecord).order_by(ExecutionLogRecord.created_at.desc())
    if plan_id:
        query = query.where(ExecutionLogRecord.plan_id == plan_id)
    if level:
        query = query.where(ExecutionLogRecord.level == level)
    result = await session.execute(query.limit(limit))
    records = result.scalars().all()
    return [
        ExecutionLogRead(
            id=r.id,
            plan_id=r.plan_id,
            tool_execution_id=r.tool_execution_id,
            level=r.level,
            message=r.message,
            metadata=r.metadata_json,
            created_at=r.created_at,
            execution_id=r.execution_id,
        )
        for r in records
    ]


@router.get("/rollback/history", response_model=list[dict])
async def list_rollback_history(
    plan_id: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
):
    engine = RollbackEngine(session)
    records = await engine.get_rollback_history(plan_id=plan_id, limit=limit)
    return [
        {
            "id": r.id,
            "checkpoint_id": r.checkpoint_id,
            "plan_id": r.plan_id,
            "repository_id": r.repository_id,
            "rollback_type": r.rollback_type,
            "status": r.status,
            "summary": r.summary,
            "restored_branch": r.restored_branch,
            "restored_git_sha": r.restored_git_sha,
            "execution_ms": r.execution_ms,
            "exception_message": r.exception_message,
            "execution_id": r.execution_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]
