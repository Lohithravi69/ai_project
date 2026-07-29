from __future__ import annotations

import pytest

from backend.services.phase3_service import Phase3Service


@pytest.mark.asyncio
async def test_tool_registry_exposes_phase3_tools(test_db):
    async with test_db() as session:
        service = Phase3Service(session)
        tool_names = {tool.name for tool in service.list_tools()}

        assert {"ReadFile", "WriteFile", "CreateBranch", "CommitChanges", "RollbackCommit", "ExecuteShell"}.issubset(tool_names)
        write_file_spec = next(tool for tool in service.list_tools() if tool.name == "WriteFile")
        assert write_file_spec.rollback_support is True
        assert write_file_spec.dry_run_support is True
        assert "path" in write_file_spec.input_schema.get("properties", {})


@pytest.fixture
async def test_db():
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from backend.database.base import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    yield session_factory
    await engine.dispose()
