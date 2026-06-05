from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database.models import GitHubConnection, RepositoryRecord
from backend.github.client import GitHubClient


class GitHubService:
    """Persist GitHub connections and repository metadata."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()

    async def connect_account(self, account_name: str, token: str) -> GitHubConnection:
        client = GitHubClient(token)
        login = client.get_user_login()
        connection = GitHubConnection(
            account_name=account_name,
            token_masked=self._mask_token(token),
            user_login=login,
            metadata_json={"source": "github", "scopes": "repo"},
        )
        self.session.add(connection)
        await self.session.commit()
        await self.session.refresh(connection)
        return connection

    async def sync_repositories(self, connection_id: str, token: str) -> list[RepositoryRecord]:
        client = GitHubClient(token)
        connection = await self.session.get(GitHubConnection, connection_id)
        if not connection:
            raise ValueError("GitHub connection not found")

        repositories: list[RepositoryRecord] = []
        for repo_info in client.list_repositories():
            existing_result = await self.session.execute(
                select(RepositoryRecord).where(RepositoryRecord.full_name == repo_info.full_name)
            )
            existing = existing_result.scalar_one_or_none()
            local_path = str(Path(self.settings.repositories_root) / repo_info.full_name.replace("/", "__"))
            if existing:
                existing.clone_url = repo_info.clone_url
                existing.default_branch = repo_info.default_branch
                existing.language_summary = {"primary": repo_info.language, "stars": repo_info.stars, "forks": repo_info.forks}
                existing.framework_summary = repo_info.metadata
                repositories.append(existing)
                continue

            repository = RepositoryRecord(
                connection_id=connection.id,
                github_id=repo_info.github_id,
                full_name=repo_info.full_name,
                clone_url=repo_info.clone_url,
                local_path=local_path,
                default_branch=repo_info.default_branch,
                language_summary={"primary": repo_info.language, "stars": repo_info.stars, "forks": repo_info.forks},
                framework_summary=repo_info.metadata,
            )
            self.session.add(repository)
            repositories.append(repository)

        await self.session.commit()
        for repository in repositories:
            await self.session.refresh(repository)
        return repositories

    @staticmethod
    def _mask_token(token: str) -> str:
        if len(token) <= 8:
            return "*" * len(token)
        return f"{token[:4]}...{token[-4:]}"
