from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database.base import Base
from backend.database.models import GitHubConnection, RepositoryRecord
from backend.github.service import GitHubService


@pytest.fixture
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    yield session_factory
    await engine.dispose()


class TestGitHubServiceConnect:
    async def test_connect_account_creates_connection(self, test_db):
        async with test_db() as session:
            with patch("backend.github.service.GitHubClient") as mock_cls:
                mock_client = MagicMock()
                mock_client.get_user_login.return_value = "testuser"
                mock_cls.return_value = mock_client

                service = GitHubService(session)
                connection = await service.connect_account("my-account", "ghp_fake_token")

                assert connection.account_name == "my-account"
                assert connection.user_login == "testuser"
                assert connection.token_masked != "ghp_fake_token"
                assert len(connection.token_masked) < len("ghp_fake_token")

    async def test_connect_uses_real_token(self, test_db):
        async with test_db() as session:
            with patch("backend.github.service.GitHubClient") as mock_cls:
                mock_client = MagicMock()
                mock_client.get_user_login.return_value = "realuser"
                mock_cls.return_value = mock_client

                service = GitHubService(session)
                connection = await service.connect_account("real-account", "ghp_real_token_1234")

                mock_cls.assert_called_once_with("ghp_real_token_1234")
                assert connection.user_login == "realuser"


class TestGitHubServiceSync:
    async def test_sync_repositories_creates_records(self, test_db):
        async with test_db() as session:
            connection = GitHubConnection(account_name="test", token_masked="***", user_login="testuser")
            session.add(connection)
            await session.commit()
            await session.refresh(connection)

            with patch("backend.github.service.GitHubClient") as mock_cls:
                mock_client = MagicMock()
                mock_repo = MagicMock()
                mock_repo.github_id = 1
                mock_repo.full_name = "testuser/repo1"
                mock_repo.clone_url = "https://github.com/testuser/repo1.git"
                mock_repo.default_branch = "main"
                mock_repo.description = "Test repo"
                mock_repo.language = "Python"
                mock_repo.stars = 10
                mock_repo.forks = 2
                mock_repo.metadata = {"private": False}
                mock_client.list_repositories.return_value = [mock_repo]
                mock_cls.return_value = mock_client

                service = GitHubService(session)
                repos = await service.sync_repositories(connection.id, "ghp_fake_token")

                assert len(repos) == 1
                assert repos[0].full_name == "testuser/repo1"
                assert repos[0].language_summary["primary"] == "Python"

    async def test_sync_repositories_connection_not_found(self, test_db):
        async with test_db() as session:
            service = GitHubService(session)
            with pytest.raises(ValueError, match="GitHub connection not found"):
                await service.sync_repositories("non-existent-id", "ghp_fake_token")

    async def test_sync_repositories_updates_existing(self, test_db):
        async with test_db() as session:
            connection = GitHubConnection(account_name="test", token_masked="***", user_login="testuser")
            session.add(connection)
            await session.commit()
            await session.refresh(connection)

            existing = RepositoryRecord(
                connection_id=connection.id,
                github_id=1,
                full_name="testuser/repo1",
                clone_url="https://github.com/testuser/repo1.git",
                local_path="/tmp/repos/testuser__repo1",
                default_branch="main",
                scan_status="synced",
            )
            session.add(existing)
            await session.commit()

            with patch("backend.github.service.GitHubClient") as mock_cls:
                mock_client = MagicMock()
                mock_repo = MagicMock()
                mock_repo.github_id = 1
                mock_repo.full_name = "testuser/repo1"
                mock_repo.clone_url = "https://github.com/testuser/repo1.git"
                mock_repo.default_branch = "develop"
                mock_repo.description = "Updated description"
                mock_repo.language = "TypeScript"
                mock_repo.stars = 20
                mock_repo.forks = 5
                mock_repo.metadata = {"private": True}
                mock_client.list_repositories.return_value = [mock_repo]
                mock_cls.return_value = mock_client

                service = GitHubService(session)
                repos = await service.sync_repositories(connection.id, "ghp_fake_token")

                assert len(repos) == 1
                assert repos[0].clone_url == "https://github.com/testuser/repo1.git"
                assert repos[0].language_summary["primary"] == "TypeScript"

    async def test_sync_multiple_repositories(self, test_db):
        async with test_db() as session:
            connection = GitHubConnection(account_name="test", token_masked="***", user_login="testuser")
            session.add(connection)
            await session.commit()
            await session.refresh(connection)

            with patch("backend.github.service.GitHubClient") as mock_cls:
                mock_client = MagicMock()
                repos_data = [
                    (1, "testuser/repo1", "Python"),
                    (2, "testuser/repo2", "TypeScript"),
                    (3, "testuser/repo3", "Rust"),
                ]
                mock_repos = []
                for gid, name, lang in repos_data:
                    r = MagicMock()
                    r.github_id = gid
                    r.full_name = name
                    r.clone_url = f"https://github.com/{name}.git"
                    r.default_branch = "main"
                    r.description = ""
                    r.language = lang
                    r.stars = 0
                    r.forks = 0
                    r.metadata = {"private": False}
                    mock_repos.append(r)
                mock_client.list_repositories.return_value = mock_repos
                mock_cls.return_value = mock_client

                service = GitHubService(session)
                repos = await service.sync_repositories(connection.id, "ghp_fake_token")

                assert len(repos) == 3
                assert repos[0].full_name == "testuser/repo1"
                assert repos[1].full_name == "testuser/repo2"
                assert repos[2].full_name == "testuser/repo3"


class TestGitHubServiceMaskToken:
    def test_mask_long_token(self):
        result = GitHubService._mask_token("ghp_abcdefghijklmnop")
        assert result == "ghp_...mnop"
        assert len(result) == 11
        assert "abcdefghijk" not in result

    def test_mask_short_token(self):
        result = GitHubService._mask_token("12345678")
        assert result == "********"

    def test_mask_empty_token(self):
        result = GitHubService._mask_token("")
        assert result == ""
