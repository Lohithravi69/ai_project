from __future__ import annotations

from pathlib import Path

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database.models import RepositoryRecord
from backend.github.client import GitHubClient
from backend.utils.repository import repository_local_path


class RepositoryService:
    """Manage repository lifecycle operations like clone, pull, and lookup."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()

    async def list_repositories(self) -> list[RepositoryRecord]:
        result = await self.session.execute(select(RepositoryRecord).order_by(RepositoryRecord.created_at.desc()))
        return list(result.scalars().all())

    async def get_repository(self, repository_id: str) -> RepositoryRecord | None:
        return await self.session.get(RepositoryRecord, repository_id)

    async def clone_or_sync_repository(self, repository_id: str, token: str) -> RepositoryRecord:
        repository = await self.session.get(RepositoryRecord, repository_id)
        if not repository:
            raise ValueError("Repository not found")

        local_path = repository_local_path(self.settings.repositories_root, repository.full_name)
        client = GitHubClient(token)

        # Git operations are blocking. Run them in a worker thread so we don't
        # block the FastAPI event loop.
        await asyncio.to_thread(
            client.clone_or_pull,
            repository.clone_url,
            local_path,
            token=token,
        )

        repository.local_path = str(local_path)
        repository.scan_status = "synced"
        await self.session.commit()
        await self.session.refresh(repository)
        return repository

    async def ensure_repository_exists(self, full_name: str, clone_url: str, connection_id: str, github_id: int, default_branch: str) -> RepositoryRecord:
        result = await self.session.execute(select(RepositoryRecord).where(RepositoryRecord.full_name == full_name))
        repository = result.scalar_one_or_none()
        if repository:
            return repository

        local_path = repository_local_path(self.settings.repositories_root, full_name)
        repository = RepositoryRecord(
            connection_id=connection_id,
            github_id=github_id,
            full_name=full_name,
            clone_url=clone_url,
            local_path=str(local_path),
            default_branch=default_branch,
        )
        self.session.add(repository)
        await self.session.commit()
        await self.session.refresh(repository)
        return repository
