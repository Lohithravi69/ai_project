from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database.base import Base
from backend.database.models import GitHubConnection, RepositoryRecord
from backend.models.schemas import ToolInvocationRequest
from backend.services.phase3_service import Phase3Service


@pytest.fixture
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    yield session_factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_write_file_dry_run_returns_diff_preview(test_db, tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "app.py").write_text("print('old')\n", encoding="utf-8")

    async with test_db() as session:
        connection = GitHubConnection(account_name="test-account", token_masked="***", user_login="tester")
        session.add(connection)
        await session.commit()
        await session.refresh(connection)

        repository = RepositoryRecord(
            connection_id=connection.id,
            github_id=1,
            full_name="test/repo",
            clone_url="https://example.com/test/repo.git",
            local_path=str(repo_root),
            default_branch="main",
            scan_status="synced",
            summary="",
            is_active=True,
        )
        session.add(repository)
        await session.commit()
        await session.refresh(repository)

        service = Phase3Service(session)
        response = await service.invoke_tool(ToolInvocationRequest(
            tool_name="WriteFile",
            repository_id=repository.id,
            inputs={
                "repository_id": repository.id,
                "path": "app.py",
                "content": "print('new')\n",
                "dry_run": True,
            },
            dry_run=True,
            reasoning="Preview a simple file update",
        ))

        assert response.dry_run is True
        assert response.success is True
        assert response.requires_approval is False
        assert response.diff_preview is not None
        assert "app.py" in response.diff_preview
        assert response.affected_files == ["app.py"]
