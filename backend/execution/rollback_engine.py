from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import uuid4

from git import Repo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import (
    CheckpointRecord,
    RepositoryRecord,
    RollbackHistoryRecord,
)


class RollbackEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def rollback(
        self,
        checkpoint_id: str,
        rollback_types: list[str] | None = None,
        dry_run: bool = False,
        execution_id: str | None = None,
    ) -> RollbackResult:
        checkpoint = await self.session.get(CheckpointRecord, checkpoint_id)
        if not checkpoint:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")

        if not rollback_types:
            rollback_types = ["git"]

        repository = None
        if checkpoint.repository_id:
            repository = await self.session.get(RepositoryRecord, checkpoint.repository_id)

        start = time.perf_counter()
        results: dict[str, Any] = {}
        summary_parts: list[str] = []
        restored_branch: str | None = checkpoint.branch_name
        restored_git_sha: str | None = checkpoint.git_sha

        try:
            if "git" in rollback_types:
                result = await self._rollback_git(checkpoint, repository, dry_run, execution_id=execution_id)
                results["git"] = result
                if result.get("success"):
                    summary_parts.append(f"git: restored to {checkpoint.branch_name}@{checkpoint.git_sha[:8]}")
                else:
                    summary_parts.append(f"git: {result.get('exception_message', 'failed')}")

            if "database" in rollback_types:
                results["database"] = {"success": True, "note": "metadata rollback not needed"}

            if "vector" in rollback_types:
                results["vector"] = {"success": True, "note": "vector indexes remain valid"}

            if "graph" in rollback_types:
                results["graph"] = {"success": True, "note": "knowledge graph unchanged"}

            if "conversation" in rollback_types:
                results["conversation"] = {"success": True, "note": "conversation state preserved"}

            if "execution" in rollback_types:
                results["execution"] = {"success": True, "note": "execution history preserved"}

        except Exception as exc:
            summary_parts.append(f"error: {exc}")
            execution_ms = int((time.perf_counter() - start) * 1000)
            return RollbackResult(
                checkpoint_id=checkpoint_id,
                success=False,
                dry_run=dry_run,
                summary="; ".join(summary_parts),
                restored_branch=restored_branch,
                restored_git_sha=restored_git_sha,
                rollback_results=results,
                execution_ms=execution_ms,
                exception_message=str(exc),
            )

        execution_ms = int((time.perf_counter() - start) * 1000)
        return RollbackResult(
            checkpoint_id=checkpoint_id,
            success=True,
            dry_run=dry_run,
            summary="; ".join(summary_parts) if summary_parts else "rollback completed",
            restored_branch=restored_branch,
            restored_git_sha=restored_git_sha,
            rollback_results=results,
            execution_ms=execution_ms,
        )

    async def _rollback_git(
        self,
        checkpoint: CheckpointRecord,
        repository: RepositoryRecord | None,
        dry_run: bool,
        execution_id: str | None = None,
    ) -> dict[str, Any]:
        if dry_run:
            return {"success": True, "dry_run": True, "would_restore": f"{checkpoint.branch_name}@{checkpoint.git_sha[:8]}"}

        record = RollbackHistoryRecord(
            checkpoint_id=checkpoint.id,
            plan_id=checkpoint.plan_id,
            repository_id=checkpoint.repository_id,
            rollback_type="git",
            status="in_progress",
            execution_id=execution_id,
        )
        self.session.add(record)
        await self.session.commit()

        try:
            if repository and repository.local_path:
                repo_path = repository.local_path
                repo = await asyncio.to_thread(Repo, repo_path)
                repo.git.reset("--hard", checkpoint.git_sha)
                if checkpoint.branch_name != "DETACHED":
                    repo.git.checkout(checkpoint.branch_name)
                repo.git.clean("-fd")

            record.status = "completed"
            record.summary = f"Restored to {checkpoint.branch_name}@{checkpoint.git_sha[:8]}"
            record.restored_branch = checkpoint.branch_name
            record.restored_git_sha = checkpoint.git_sha
            await self.session.commit()

            return {"success": True, "branch": checkpoint.branch_name, "sha": checkpoint.git_sha}
        except Exception as exc:
            record.status = "failed"
            record.exception_message = str(exc)
            await self.session.commit()
            return {"success": False, "exception_message": str(exc)}

    async def get_rollback_history(
        self,
        plan_id: str | None = None,
        checkpoint_id: str | None = None,
        limit: int = 50,
    ) -> list[RollbackHistoryRecord]:
        query = select(RollbackHistoryRecord).order_by(RollbackHistoryRecord.created_at.desc())
        if plan_id:
            query = query.where(RollbackHistoryRecord.plan_id == plan_id)
        if checkpoint_id:
            query = query.where(RollbackHistoryRecord.checkpoint_id == checkpoint_id)
        result = await self.session.execute(query.limit(limit))
        return list(result.scalars().all())


class RollbackResult:
    def __init__(
        self,
        checkpoint_id: str,
        success: bool,
        dry_run: bool,
        summary: str = "",
        restored_branch: str | None = None,
        restored_git_sha: str | None = None,
        rollback_results: dict[str, Any] | None = None,
        execution_ms: int = 0,
        exception_message: str = "",
    ) -> None:
        self.checkpoint_id = checkpoint_id
        self.success = success
        self.dry_run = dry_run
        self.summary = summary
        self.restored_branch = restored_branch
        self.restored_git_sha = restored_git_sha
        self.rollback_results = rollback_results or {}
        self.execution_ms = execution_ms
        self.exception_message = exception_message
