from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.agents.orchestrator import AgentOrchestrator
from backend.database.base import Base
from backend.models.schemas import AgentRunRequest


@pytest.fixture
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    yield session_factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_run_full_pipeline_plan_only(test_db):
    async with test_db() as session:
        orchestrator = AgentOrchestrator(session)
        response = await orchestrator.run_full_pipeline(
            AgentRunRequest(request_text="Read the main file", mode="plan-only")
        )
        assert response.execution_id is not None
        assert response.plan_id is not None
        assert len(response.plan_id) > 0
        assert response.status == "completed"
        assert isinstance(response.agent_trace, list)


@pytest.mark.asyncio
async def test_get_status_returns_valid_response(test_db):
    async with test_db() as session:
        orchestrator = AgentOrchestrator(session)
        response = await orchestrator.run_full_pipeline(
            AgentRunRequest(request_text="List all files", mode="plan-only")
        )
        status = await orchestrator.get_status(response.execution_id)
        assert status is not None
        assert status.execution_id == response.execution_id
        assert status.plan_id == response.plan_id
        assert status.agent_status == "completed"


@pytest.mark.asyncio
async def test_get_status_returns_none_for_missing(test_db):
    async with test_db() as session:
        orchestrator = AgentOrchestrator(session)
        status = await orchestrator.get_status("nonexistent-id")
        assert status is None


@pytest.mark.asyncio
async def test_get_trace_returns_list(test_db):
    async with test_db() as session:
        orchestrator = AgentOrchestrator(session)
        response = await orchestrator.run_full_pipeline(
            AgentRunRequest(request_text="Show me the code", mode="plan-only")
        )
        trace = await orchestrator.get_trace(response.plan_id)
        assert isinstance(trace, list)


@pytest.mark.asyncio
async def test_get_trace_returns_empty_for_missing(test_db):
    async with test_db() as session:
        orchestrator = AgentOrchestrator(session)
        trace = await orchestrator.get_trace("nonexistent-plan")
        assert trace == []
