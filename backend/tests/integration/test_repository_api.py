from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from backend.database.base import Base
from backend.database.models import GitHubConnection, RepositoryRecord
from backend.main import app


@pytest.fixture
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    async def get_session():
        async with async_session() as session:
            yield session

    app.dependency_overrides[__import__("backend.database.session", fromlist=["get_session"]).get_session] = get_session
    yield async_session
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
async def seeded_db(test_db):
    async with test_db() as session:
        connection = GitHubConnection(account_name="test-account", token_masked="ghp_...abcd", user_login="testuser")
        session.add(connection)
        await session.commit()
        await session.refresh(connection)

        repos = [
            RepositoryRecord(
                connection_id=connection.id,
                github_id=i,
                full_name=f"testuser/repo{i}",
                clone_url=f"https://github.com/testuser/repo{i}.git",
                local_path=f"/tmp/repos/testuser__repo{i}",
                default_branch="main",
                language_summary={"primary": "Python" if i % 2 == 0 else "TypeScript"},
                scan_status="synced" if i == 1 else "pending",
                is_active=True,
            )
            for i in range(1, 4)
        ]
        for repo in repos:
            session.add(repo)
        await session.commit()
    return test_db


class TestListRepositories:
    def test_list_repositories_empty(self, client, test_db):
        response = client.get("/api/repositories")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_repositories_returns_all(self, client, seeded_db):
        response = client.get("/api/repositories")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        names = [r["full_name"] for r in data]
        assert "testuser/repo1" in names
        assert "testuser/repo2" in names
        assert "testuser/repo3" in names

    def test_list_repositories_ordered_by_created_at(self, client, seeded_db):
        response = client.get("/api/repositories")
        assert response.status_code == 200
        data = response.json()
        created_ats = [r["created_at"] for r in data]
        assert created_ats == sorted(created_ats, reverse=True)


class TestGetRepositorySummary:
    def test_summary_not_found(self, client):
        response = client.get("/api/repositories/non-existent-id/summary")
        assert response.status_code == 404

    def test_summary_found(self, client, seeded_db):
        async def _get_repo_id():
            async with seeded_db() as session:
                result = await session.execute(select(RepositoryRecord).where(RepositoryRecord.full_name == "testuser/repo2"))
                return result.scalar_one().id

        repo_id = asyncio.run(_get_repo_id())
        response = client.get(f"/api/repositories/{repo_id}/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["repository_name"] == "testuser/repo2"
        assert data["language_summary"]["primary"] == "Python"


class TestGetRepositoryFiles:
    def test_files_empty(self, client, seeded_db):
        async def _get_repo_id():
            async with seeded_db() as session:
                result = await session.execute(select(RepositoryRecord).where(RepositoryRecord.full_name == "testuser/repo1"))
                return result.scalar_one().id

        repo_id = asyncio.run(_get_repo_id())
        response = client.get(f"/api/repositories/{repo_id}/files")
        assert response.status_code == 200
        data = response.json()
        assert data["files"] == []


class TestGitHubConnect:
    def test_connect_success(self, client, test_db):
        with patch("backend.github.service.GitHubClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.get_user_login.return_value = "github_testuser"
            mock_cls.return_value = mock_client

            response = client.post(
                "/api/github/connect",
                json={"account_name": "my-github", "token": "ghp_valid_token"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["user_login"] == "github_testuser"
            assert data["account_name"] == "my-github"

    def test_connect_with_invalid_token(self, client, test_db):
        with patch("backend.github.service.GitHubClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.get_user_login.side_effect = Exception("Bad credentials")
            mock_cls.return_value = mock_client

            response = client.post(
                "/api/github/connect",
                json={"account_name": "my-github", "token": "ghp_bad_token"},
            )
            assert response.status_code == 400


class TestGitHubSync:
    def test_sync_repositories(self, client, seeded_db):
        async def _get_connection_id():
            async with seeded_db() as session:
                result = await session.execute(select(GitHubConnection))
                return result.scalar_one().id

        conn_id = asyncio.run(_get_connection_id())

        with patch("backend.github.service.GitHubClient") as mock_cls:
            mock_client = MagicMock()
            mock_repo = MagicMock()
            mock_repo.github_id = 100
            mock_repo.full_name = "testuser/new-repo"
            mock_repo.clone_url = "https://github.com/testuser/new-repo.git"
            mock_repo.default_branch = "main"
            mock_repo.description = ""
            mock_repo.language = "Go"
            mock_repo.stars = 0
            mock_repo.forks = 0
            mock_repo.metadata = {"private": False}
            mock_client.list_repositories.return_value = [mock_repo]
            mock_cls.return_value = mock_client

            response = client.post(
                "/api/github/sync",
                json={"connection_id": conn_id, "token": "ghp_valid_token"},
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data["repositories"]) == 1
            assert data["repositories"][0]["full_name"] == "testuser/new-repo"

    def test_sync_connection_not_found(self, client):
        response = client.post(
            "/api/github/sync",
            json={"connection_id": "non-existent", "token": "ghp_valid_token"},
        )
        assert response.status_code == 404


class TestRepositorySync:
    def test_sync_repository_clones(self, client, seeded_db):
        async def _get_repo_id():
            async with seeded_db() as session:
                result = await session.execute(select(RepositoryRecord).where(RepositoryRecord.full_name == "testuser/repo1"))
                return result.scalar_one().id

        repo_id = asyncio.run(_get_repo_id())

        with patch("backend.services.repository_service.GitHubClient") as mock_gh_cls:
            mock_client = MagicMock()
            mock_client.clone_or_pull.return_value = "/tmp/repos/testuser__repo1"
            mock_gh_cls.return_value = mock_client

            response = client.post(
                f"/api/repositories/{repo_id}/sync",
                content='"ghp_valid_token"',
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["scan_status"] == "synced"

    def test_sync_repository_not_found(self, client, test_db):
        response = client.post(
            "/api/repositories/non-existent/sync",
            content='"ghp_valid_token"',
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400
