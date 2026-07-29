from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.orchestrator import AgentOrchestrator
from backend.database.session import get_session
from backend.models.schemas import AgentRunRequest, AgentRunResponse, AgentStatusResponse, AgentTraceEntry

router = APIRouter(prefix="/api/v5", tags=["agents"])


@router.post("/agents/run", response_model=AgentRunResponse)
async def run_agents(payload: AgentRunRequest, session: AsyncSession = Depends(get_session)):
    orchestrator = AgentOrchestrator(session)
    return await orchestrator.run_full_pipeline(payload)


@router.get("/agents/{execution_id}/status", response_model=AgentStatusResponse)
async def get_agent_status(execution_id: str, session: AsyncSession = Depends(get_session)):
    orchestrator = AgentOrchestrator(session)
    result = await orchestrator.get_status(execution_id)
    if not result:
        raise HTTPException(status_code=404, detail="Execution not found")
    return result


@router.get("/agents/{plan_id}/trace", response_model=list[AgentTraceEntry])
async def get_agent_trace(plan_id: str, session: AsyncSession = Depends(get_session)):
    orchestrator = AgentOrchestrator(session)
    return await orchestrator.get_trace(plan_id)
