from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from git import Repo
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database.models import RepositoryRecord, WorkspaceRecord


class WorkspaceManager:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()

    async def create_workspace(
        self,
        repository_id: str,
        plan_id: str | None = None,
        branch_name: str | None = None,
        base_branch: str | None = None,
        execution_id: str | None = None,
    ) -> WorkspaceRecord:
        repository = await self.session.get(RepositoryRecord, repository_id)
        if not repository:
            raise ValueError(f"Repository not found: {repository_id}")

        repo = await asyncio.to_thread(Repo, repository.local_path)
        base = base_branch or repository.default_branch
        branch = branch_name or f"workspace/{uuid4().hex[:12]}"

        workspace_dir = Path(self.settings.repositories_root) / "workspaces" / repository.full_name.replace("/", "__") / branch
        workspace_dir.mkdir(parents=True, exist_ok=True)

        ws = WorkspaceRecord(
            plan_id=plan_id,
            repository_id=repository_id,
            repository_full_name=repository.full_name,
            workspace_path=str(workspace_dir),
            branch_name=branch,
            base_branch=base,
            status="created",
            execution_id=execution_id,
        )
        self.session.add(ws)
        await self.session.commit()
        await self.session.refresh(ws)
        return ws

    async def clone_to_workspace(self, workspace: WorkspaceRecord) -> WorkspaceRecord:
        repository = await self.session.get(RepositoryRecord, workspace.repository_id)
        if not repository:
            raise ValueError(f"Repository not found: {workspace.repository_id}")

        workspace_path = Path(workspace.workspace_path)
        if workspace_path.exists():
            workspace.status = "cloned"
            await self.session.commit()
            return workspace

        workspace_path.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(
            Repo.clone_from, repository.clone_url, str(workspace_path)
        )
        repo = await asyncio.to_thread(Repo, str(workspace_path))
        repo.git.checkout(workspace.base_branch)
        repo.git.checkout("-b", workspace.branch_name)

        workspace.status = "cloned"
        await self.session.commit()
        await self.session.refresh(workspace)
        return workspace

    async def get_workspace(self, workspace_id: str) -> WorkspaceRecord | None:
        return await self.session.get(WorkspaceRecord, workspace_id)

    async def list_workspaces(
        self,
        repository_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[WorkspaceRecord]:
        from sqlalchemy import select

        query = select(WorkspaceRecord).order_by(WorkspaceRecord.created_at.desc())
        if repository_id:
            query = query.where(WorkspaceRecord.repository_id == repository_id)
        if status:
            query = query.where(WorkspaceRecord.status == status)
        result = await self.session.execute(query.limit(limit))
        return list(result.scalars().all())

    async def commit_workspace_changes(
        self, workspace: WorkspaceRecord, message: str
    ) -> str:
        repo = await asyncio.to_thread(Repo, workspace.workspace_path)
        repo.git.add(A=True)
        repo.index.commit(message)
        sha = repo.head.commit.hexsha
        workspace.commit_sha = sha
        workspace.status = "committed"
        await self.session.commit()
        return sha

    async def push_and_create_pr(self, workspace: WorkspaceRecord) -> dict[str, Any]:
        repo = await asyncio.to_thread(Repo, workspace.workspace_path)
        origin = repo.remotes.origin
        await asyncio.to_thread(origin.push, workspace.branch_name)
        workspace.status = "pushed"
        await self.session.commit()
        return {"branch": workspace.branch_name, "status": "pushed"}

    async def destroy_workspace(self, workspace: WorkspaceRecord) -> None:
        workspace_path = Path(workspace.workspace_path)
        if workspace_path.exists():
            await asyncio.to_thread(shutil.rmtree, str(workspace_path))
        workspace.status = "destroyed"
        await self.session.commit()
