from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from git import Repo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import CheckpointRecord, ExecutionPlanRecord, WorkspaceRecord


class CheckpointEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_checkpoint(
        self,
        *,
        plan_id: str | None = None,
        workspace_id: str | None = None,
        repository_id: str | None = None,
        repo_path: str | None = None,
        tool_name: str = "",
        modified_files: list[str] | None = None,
        reasoning: str = "",
        metadata: dict[str, Any] | None = None,
        execution_id: str | None = None,
    ) -> str:
        branch_name = "unknown"
        git_sha = "unknown"

        if repo_path:
            try:
                repo = Repo(repo_path)
                branch_name = repo.active_branch.name if not repo.head.is_detached else "DETACHED"
                git_sha = repo.head.commit.hexsha
            except Exception:
                pass

        plan_json: dict[str, Any] = {}
        if plan_id:
            record = await self.session.get(ExecutionPlanRecord, plan_id)
            if record:
                plan_json = record.plan_json

        checkpoint = CheckpointRecord(
            plan_id=plan_id,
            workspace_id=workspace_id,
            repository_id=repository_id,
            branch_name=branch_name,
            git_sha=git_sha,
            tool_name=tool_name,
            modified_files_json=sorted(set(modified_files or [])),
            reasoning=reasoning,
            plan_json=plan_json,
            metadata_json=metadata or {},
            execution_id=execution_id,
        )
        self.session.add(checkpoint)
        await self.session.commit()
        await self.session.refresh(checkpoint)
        return checkpoint.id

    async def get_checkpoint(self, checkpoint_id: str) -> CheckpointRecord | None:
        return await self.session.get(CheckpointRecord, checkpoint_id)

    async def list_checkpoints(
        self,
        plan_id: str | None = None,
        workspace_id: str | None = None,
        repository_id: str | None = None,
        limit: int = 100,
    ) -> list[CheckpointRecord]:
        query = select(CheckpointRecord).order_by(CheckpointRecord.created_at.desc())
        if plan_id:
            query = query.where(CheckpointRecord.plan_id == plan_id)
        if workspace_id:
            query = query.where(CheckpointRecord.workspace_id == workspace_id)
        if repository_id:
            query = query.where(CheckpointRecord.repository_id == repository_id)
        result = await self.session.execute(query.limit(limit))
        return list(result.scalars().all())

    async def get_latest_checkpoint(self, plan_id: str) -> CheckpointRecord | None:
        query = (
            select(CheckpointRecord)
            .where(CheckpointRecord.plan_id == plan_id)
            .order_by(CheckpointRecord.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
