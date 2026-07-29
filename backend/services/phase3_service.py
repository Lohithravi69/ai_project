from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path
from typing import Any
from uuid import uuid4

from git import InvalidGitRepositoryError, Repo
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database.models import ActionPlanRecord, ExecutionCheckpoint, RepositoryRecord, ToolInvocationLog
from backend.embeddings.chroma_service import ChromaService
from backend.embeddings.ollama_client import OllamaClient
from backend.models.schemas import (
    ActionPlanCreateRequest,
    ActionPlanRead,
    CheckpointRead,
    PlanApprovalRequest,
    PlanStepRead,
    RollbackCommitInput,
    RollbackResponse,
    ToolInvocationRequest,
    ToolInvocationResponse,
    ToolSpecRead,
)
from backend.services.repository_service import RepositoryService
from backend.services.repository_sync_service import RepositorySyncService
from backend.utils.files import hash_content, iter_text_files, safe_read_text


class ReadFileInput(BaseModel):
    repository_id: str
    path: str
    dry_run: bool = True


class WriteFileInput(BaseModel):
    repository_id: str
    path: str
    content: str
    dry_run: bool = True


class SearchRepositoryInput(BaseModel):
    repository_id: str
    query: str
    path_prefix: str | None = None
    regex: bool = False
    case_sensitive: bool = False
    dry_run: bool = True


class ListFilesInput(BaseModel):
    repository_id: str
    path: str = ""
    dry_run: bool = True


class GitStatusInput(BaseModel):
    repository_id: str
    dry_run: bool = True


class GitDiffInput(BaseModel):
    repository_id: str
    ref_a: str | None = None
    ref_b: str | None = None
    path: str | None = None
    dry_run: bool = True


class CreateBranchInput(BaseModel):
    repository_id: str
    branch_name: str
    from_ref: str | None = None
    dry_run: bool = True


class CommitChangesInput(BaseModel):
    repository_id: str
    message: str
    dry_run: bool = True


class RollbackCommitInput(BaseModel):
    checkpoint_id: str
    dry_run: bool = False


class ExecuteTestsInput(BaseModel):
    repository_id: str
    command: str = "pytest"
    dry_run: bool = True


class ExecuteShellInput(BaseModel):
    repository_id: str
    command: str
    dry_run: bool = True


class QueryVectorStoreInput(BaseModel):
    repository_id: str
    query: str
    top_k: int = 5
    dry_run: bool = True


class QueryPostgresInput(BaseModel):
    sql: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = True


@dataclass(slots=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    permission_level: str
    timeout_seconds: int = 30
    rollback_supported: bool = False
    dry_run_supported: bool = True

    def as_read_model(self) -> ToolSpecRead:
        return ToolSpecRead(
            name=self.name,
            description=self.description,
            input_schema=self.input_model.model_json_schema(),
            output_schema=ToolInvocationResponse.model_json_schema(),
            permission_level=self.permission_level,
            timeout_seconds=self.timeout_seconds,
            rollback_support=self.rollback_supported,
            dry_run_support=self.dry_run_supported,
        )


class Phase3Service:
    """Tool-registry driven planning, execution, and rollback workflow for Phase 3."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()
        self.repository_service = RepositoryService(session)
        self.chroma = ChromaService(self.settings.chroma_persist_directory)
        self.ollama = OllamaClient(self.settings.ollama_base_url, self.settings.ollama_chat_model, self.settings.ollama_embed_model)
        self._tool_specs = self._build_tool_specs()

    def list_tools(self) -> list[ToolSpecRead]:
        return [spec.as_read_model() for spec in self._tool_specs.values()]

    async def create_plan(self, request: ActionPlanCreateRequest) -> ActionPlanRead:
        plan = self._build_plan(request)
        record = ActionPlanRecord(
            id=plan.plan_id,
            repository_id=request.repository_ids[0] if request.repository_ids else None,
            objective=plan.objective,
            reasoning=plan.reasoning,
            affected_repositories_json=plan.affected_repositories,
            affected_files_json=plan.affected_files,
            estimated_risk=plan.estimated_risk,
            required_tools_json=plan.required_tools,
            rollback_strategy=plan.rollback_strategy,
            approval_status=plan.approval_status,
            execution_order_json=[step.model_dump() for step in plan.execution_order],
            plan_json=plan.model_dump(),
        )
        self.session.add(record)
        await self.session.commit()
        return plan

    async def approve_plan(self, plan_id: str, request: PlanApprovalRequest) -> ActionPlanRead:
        record = await self.session.get(ActionPlanRecord, plan_id)
        if not record:
            raise ValueError("Plan not found")
        record.approval_status = "approved" if request.approved else "rejected"
        await self.session.commit()
        return self._plan_from_record(record)

    async def get_plan(self, plan_id: str) -> ActionPlanRead:
        record = await self.session.get(ActionPlanRecord, plan_id)
        if not record:
            raise ValueError("Plan not found")
        return self._plan_from_record(record)

    async def list_checkpoints(self, repository_id: str | None = None) -> list[CheckpointRead]:
        query = select(ExecutionCheckpoint).order_by(ExecutionCheckpoint.created_at.desc())
        if repository_id:
            query = query.where(ExecutionCheckpoint.repository_id == repository_id)
        result = await self.session.execute(query.limit(100))
        return [self._checkpoint_from_record(record) for record in result.scalars().all()]

    async def invoke_tool(self, request: ToolInvocationRequest) -> ToolInvocationResponse:
        spec = self._tool_specs.get(request.tool_name)
        if not spec:
            raise ValueError(f"Unknown tool: {request.tool_name}")

        validated = spec.input_model.model_validate(request.inputs)
        normalized = validated.model_dump()
        repository = await self._resolve_repository(normalized.get("repository_id")) if normalized.get("repository_id") else None
        if repository is None and spec.permission_level != "read" and request.tool_name not in {"QueryPostgres"}:
            raise ValueError("Repository not found")

        start = time.perf_counter()
        checkpoint_id: str | None = None
        requires_approval = False
        exception_message = ""
        success = False
        result: ToolInvocationResponse | None = None

        try:
            if self._requires_checkpoint(spec, request.dry_run) and not await self._plan_is_approved(request.plan_id):
                requires_approval = True
                preview = await self._execute_tool(spec, normalized, dry_run=True, repository=repository, plan_id=request.plan_id)
                result = preview.model_copy(update={"requires_approval": True, "dry_run": True})
                success = True
                return result

            if self._requires_checkpoint(spec, request.dry_run) and not request.dry_run:
                checkpoint_id = await self._create_checkpoint(repository, request.plan_id, request.reasoning, normalized)

            result = await self._execute_tool(spec, normalized, dry_run=request.dry_run, repository=repository, plan_id=request.plan_id)
            if checkpoint_id:
                result = result.model_copy(update={"checkpoint_id": checkpoint_id})
                if request.plan_id:
                    await self._mark_plan_executed(request.plan_id)
            success = True
            return result
        except Exception as exc:
            exception_message = str(exc)
            raise
        finally:
            execution_ms = int((time.perf_counter() - start) * 1000)
            if result is None:
                result = ToolInvocationResponse(
                    tool_name=request.tool_name,
                    dry_run=request.dry_run,
                    success=success,
                    execution_ms=execution_ms,
                    result={},
                    affected_files=[],
                    diff_preview=None,
                    estimated_impact="",
                    risks=[],
                    checkpoint_id=checkpoint_id,
                    requires_approval=requires_approval,
                    exception_message=exception_message,
                )
            else:
                result = result.model_copy(
                    update={
                        "success": success,
                        "execution_ms": execution_ms,
                        "checkpoint_id": checkpoint_id or result.checkpoint_id,
                        "requires_approval": requires_approval or result.requires_approval,
                        "exception_message": exception_message or result.exception_message,
                    }
                )
            await self._log_invocation(
                plan_id=request.plan_id,
                checkpoint_id=checkpoint_id,
                repository_id=repository.id if repository else None,
                tool_name=request.tool_name,
                inputs=normalized,
                outputs=result.model_dump(mode="json"),
                dry_run=result.dry_run,
                success=success,
                execution_ms=execution_ms,
                exception_message=exception_message,
            )

    async def rollback_checkpoint(self, request: RollbackCommitInput) -> RollbackResponse:
        response, checkpoint_before_rollback, repository_id, _repository_name = await self._rollback_core(request)
        await self._log_invocation(
            plan_id=checkpoint.plan_id,
            checkpoint_id=checkpoint_before_rollback,
            repository_id=repository_id,
            tool_name="RollbackCommit",
            inputs=request.model_dump(),
            outputs=response.model_dump(mode="json"),
            dry_run=request.dry_run,
            success=response.success,
            execution_ms=response.execution_ms,
            exception_message=response.exception_message,
        )
        return response

    async def _rollback_core(self, request: RollbackCommitInput) -> tuple[RollbackResponse, str | None, str | None, str | None]:
        checkpoint = await self.session.get(ExecutionCheckpoint, request.checkpoint_id)
        if not checkpoint:
            raise ValueError("Checkpoint not found")
        if not checkpoint.repository_id:
            raise ValueError("Checkpoint does not reference a repository")
        repository = await self._resolve_repository(checkpoint.repository_id)
        if not repository:
            raise ValueError("Repository not found")

        start = time.perf_counter()
        dry_run = request.dry_run
        exception_message = ""
        summary = ""
        restored_branch: str | None = checkpoint.branch_name
        restored_git_sha: str | None = checkpoint.git_sha
        success = False
        checkpoint_before_rollback: str | None = None

        try:
            if dry_run:
                summary = f"Would restore {repository.full_name} to {checkpoint.branch_name}@{checkpoint.git_sha}"
                success = True
                execution_ms = int((time.perf_counter() - start) * 1000)
                return RollbackResponse(
                    checkpoint_id=checkpoint.id,
                    repository_id=repository.id,
                    success=True,
                    dry_run=True,
                    restored_branch=restored_branch,
                    restored_git_sha=restored_git_sha,
                    summary=summary,
                    execution_ms=execution_ms,
                ), None, repository.id, repository.full_name

            checkpoint_before_rollback = await self._create_checkpoint(
                repository,
                checkpoint.plan_id,
                "rollback_before_restore",
                {"checkpoint_id": checkpoint.id, "reason": "rollback"},
            )
            repo = await self._open_repo(repository.local_path)
            await asyncio.to_thread(self._restore_repository_state, repo, checkpoint.branch_name, checkpoint.git_sha)
            await RepositorySyncService(self.session).sync_repository(repository.id, pull_remote=False)
            summary = f"Restored {repository.full_name} to {checkpoint.branch_name}@{checkpoint.git_sha}"
            success = True
            execution_ms = int((time.perf_counter() - start) * 1000)
            return RollbackResponse(
                checkpoint_id=checkpoint.id,
                repository_id=repository.id,
                success=True,
                dry_run=False,
                restored_branch=restored_branch,
                restored_git_sha=restored_git_sha,
                summary=summary,
                execution_ms=execution_ms,
            ), checkpoint_before_rollback, repository.id, repository.full_name
        except Exception as exc:
            exception_message = str(exc)
            raise

    async def _execute_tool(
        self,
        spec: ToolSpec,
        payload: dict[str, Any],
        *,
        dry_run: bool,
        repository: RepositoryRecord | None,
        plan_id: str | None,
    ) -> ToolInvocationResponse:
        handlers = {
            "ReadFile": self._read_file,
            "WriteFile": self._write_file,
            "SearchRepository": self._search_repository,
            "ListFiles": self._list_files,
            "GitStatus": self._git_status,
            "GitDiff": self._git_diff,
            "CreateBranch": self._create_branch,
            "CommitChanges": self._commit_changes,
            "RollbackCommit": self._rollback_tool,
            "ExecuteTests": self._execute_tests,
            "ExecuteShell": self._execute_shell,
            "QueryVectorStore": self._query_vector_store,
            "QueryPostgres": self._query_postgres,
        }
        handler = handlers.get(spec.name)
        if not handler:
            raise ValueError(f"No handler registered for {spec.name}")
        return await handler(payload, dry_run=dry_run, repository=repository, plan_id=plan_id)

    async def _read_file(self, payload: dict[str, Any], *, dry_run: bool, repository: RepositoryRecord | None, plan_id: str | None) -> ToolInvocationResponse:
        repo = self._require_repository(repository)
        path = self._resolve_repo_path(repo, payload["path"])
        content = await asyncio.to_thread(safe_read_text, path, self.settings.max_file_size_bytes)
        metadata = {
            "path": str(path.relative_to(Path(repo.local_path))) if path.exists() else payload["path"],
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "hash": hash_content(content) if content else "",
        }
        return ToolInvocationResponse(
            tool_name="ReadFile",
            dry_run=dry_run,
            success=True,
            execution_ms=0,
            result={"content": content, "metadata": metadata},
            affected_files=[payload["path"]],
            estimated_impact="read-only",
            risks=[],
        )

    async def _write_file(self, payload: dict[str, Any], *, dry_run: bool, repository: RepositoryRecord | None, plan_id: str | None) -> ToolInvocationResponse:
        repo = self._require_repository(repository)
        path = self._resolve_repo_path(repo, payload["path"])
        existing = await asyncio.to_thread(safe_read_text, path, self.settings.max_file_size_bytes) if path.exists() else ""
        diff_preview = "\n".join(
            unified_diff(
                existing.splitlines(),
                payload["content"].splitlines(),
                fromfile=str(path),
                tofile=f"{path} (proposed)",
                lineterm="",
            )
        )
        if dry_run:
            return ToolInvocationResponse(
                tool_name="WriteFile",
                dry_run=True,
                success=True,
                execution_ms=0,
                result={"path": str(path), "would_write": True},
                affected_files=[payload["path"]],
                diff_preview=diff_preview,
                estimated_impact="modifies one file",
                risks=["content overwrite"],
            )

        await asyncio.to_thread(self._write_text_file, path, payload["content"])
        return ToolInvocationResponse(
            tool_name="WriteFile",
            dry_run=False,
            success=True,
            execution_ms=0,
            result={"path": str(path), "written": True, "content_hash": hash_content(payload["content"])},
            affected_files=[payload["path"]],
            diff_preview=diff_preview,
            estimated_impact="modifies one file",
            risks=["content overwrite"],
        )

    async def _search_repository(self, payload: dict[str, Any], *, dry_run: bool, repository: RepositoryRecord | None, plan_id: str | None) -> ToolInvocationResponse:
        repo = self._require_repository(repository)
        root = Path(repo.local_path)
        pattern = payload["query"] if payload.get("regex") else re.escape(payload["query"])
        flags = 0 if payload.get("case_sensitive") else re.IGNORECASE
        compiled = re.compile(pattern, flags)
        matches: list[dict[str, Any]] = []
        for file_path in iter_text_files(root):
            if payload.get("path_prefix") and not str(file_path).startswith(str(root / payload["path_prefix"])):
                continue
            text_content = await asyncio.to_thread(safe_read_text, file_path, self.settings.max_file_size_bytes)
            if not text_content:
                continue
            for line_number, line in enumerate(text_content.splitlines(), start=1):
                if compiled.search(line):
                    matches.append({"path": str(file_path.relative_to(root)), "line": line_number, "text": line.strip()})
                    if len(matches) >= 50:
                        break
            if len(matches) >= 50:
                break
        return ToolInvocationResponse(
            tool_name="SearchRepository",
            dry_run=dry_run,
            success=True,
            execution_ms=0,
            result={"matches": matches, "match_count": len(matches)},
            affected_files=[match["path"] for match in matches],
            estimated_impact="read-only search",
            risks=[],
        )

    async def _list_files(self, payload: dict[str, Any], *, dry_run: bool, repository: RepositoryRecord | None, plan_id: str | None) -> ToolInvocationResponse:
        repo = self._require_repository(repository)
        root = Path(repo.local_path)
        base = self._resolve_repo_path(repo, payload.get("path", "")) if payload.get("path") else root
        files: list[str] = []
        for file_path in base.rglob("*"):
            if file_path.is_file():
                try:
                    files.append(str(file_path.relative_to(root)))
                except ValueError:
                    files.append(str(file_path))
        return ToolInvocationResponse(
            tool_name="ListFiles",
            dry_run=dry_run,
            success=True,
            execution_ms=0,
            result={"files": sorted(files)},
            affected_files=[],
            estimated_impact="read-only listing",
            risks=[],
        )

    async def _git_status(self, payload: dict[str, Any], *, dry_run: bool, repository: RepositoryRecord | None, plan_id: str | None) -> ToolInvocationResponse:
        repo = await self._open_repo(self._require_repository(repository).local_path)
        status = await asyncio.to_thread(lambda: repo.git.status("--short"))
        return ToolInvocationResponse(
            tool_name="GitStatus",
            dry_run=dry_run,
            success=True,
            execution_ms=0,
            result={"status": status},
            affected_files=self._parse_status_files(status),
            estimated_impact="read-only git metadata",
            risks=[],
        )

    async def _git_diff(self, payload: dict[str, Any], *, dry_run: bool, repository: RepositoryRecord | None, plan_id: str | None) -> ToolInvocationResponse:
        repo = await self._open_repo(self._require_repository(repository).local_path)
        def _diff() -> str:
            if payload.get("ref_a") and payload.get("ref_b"):
                diff_args = [payload["ref_a"], payload["ref_b"]]
                if payload.get("path"):
                    diff_args.extend(["--", payload["path"]])
                return repo.git.diff(*diff_args)
            if payload.get("ref_a"):
                diff_args = [payload["ref_a"]]
                if payload.get("path"):
                    diff_args.extend(["--", payload["path"]])
                return repo.git.diff(*diff_args)
            return repo.git.diff()

        diff = await asyncio.to_thread(_diff)
        return ToolInvocationResponse(
            tool_name="GitDiff",
            dry_run=dry_run,
            success=True,
            execution_ms=0,
            result={"diff": diff},
            affected_files=[payload["path"]] if payload.get("path") else [],
            diff_preview=diff,
            estimated_impact="read-only diff",
            risks=[],
        )

    async def _create_branch(self, payload: dict[str, Any], *, dry_run: bool, repository: RepositoryRecord | None, plan_id: str | None) -> ToolInvocationResponse:
        repo = await self._open_repo(self._require_repository(repository).local_path)
        current_branch = self._current_branch_name(repo)
        if dry_run:
            return ToolInvocationResponse(
                tool_name="CreateBranch",
                dry_run=True,
                success=True,
                execution_ms=0,
                result={"branch_name": payload["branch_name"], "from_ref": payload.get("from_ref"), "current_branch": current_branch},
                estimated_impact="changes repository branch pointer",
                risks=["branch switch"],
            )

        await asyncio.to_thread(self._checkout_branch, repo, payload["branch_name"], payload.get("from_ref"))
        return ToolInvocationResponse(
            tool_name="CreateBranch",
            dry_run=False,
            success=True,
            execution_ms=0,
            result={"branch_name": payload["branch_name"], "from_ref": payload.get("from_ref"), "current_branch": payload["branch_name"]},
            estimated_impact="changes repository branch pointer",
            risks=["branch switch"],
        )

    async def _commit_changes(self, payload: dict[str, Any], *, dry_run: bool, repository: RepositoryRecord | None, plan_id: str | None) -> ToolInvocationResponse:
        repo = await self._open_repo(self._require_repository(repository).local_path)
        if dry_run:
            staged = await asyncio.to_thread(lambda: repo.git.diff("--cached"))
            return ToolInvocationResponse(
                tool_name="CommitChanges",
                dry_run=True,
                success=True,
                execution_ms=0,
                result={"message": payload["message"], "staged_diff": staged},
                diff_preview=staged,
                estimated_impact="writes git history",
                risks=["commit history change"],
            )

        await asyncio.to_thread(self._commit_repo, repo, payload["message"])
        head_sha = repo.head.commit.hexsha
        return ToolInvocationResponse(
            tool_name="CommitChanges",
            dry_run=False,
            success=True,
            execution_ms=0,
            result={"message": payload["message"], "commit_sha": head_sha},
            estimated_impact="writes git history",
            risks=["commit history change"],
        )

    async def _rollback_tool(self, payload: dict[str, Any], *, dry_run: bool, repository: RepositoryRecord | None, plan_id: str | None) -> ToolInvocationResponse:
        response = await self.rollback_checkpoint(RollbackCommitInput.model_validate(payload))
        return ToolInvocationResponse(
            tool_name="RollbackCommit",
            dry_run=response.dry_run,
            success=response.success,
            execution_ms=response.execution_ms,
            result=response.model_dump(mode="json"),
            estimated_impact="restores repository state and indexes",
            risks=["state restoration"],
        )

    async def _execute_tests(self, payload: dict[str, Any], *, dry_run: bool, repository: RepositoryRecord | None, plan_id: str | None) -> ToolInvocationResponse:
        repo = self._require_repository(repository)
        command = payload.get("command") or "pytest"
        args = self._validated_shell_args(command, tests_only=True)
        if dry_run:
            return ToolInvocationResponse(
                tool_name="ExecuteTests",
                dry_run=True,
                success=True,
                execution_ms=0,
                result={"command": command, "args": args, "would_run": True},
                estimated_impact="runs tests only",
                risks=["test runtime"],
            )
        completed = await self._run_shell_command(args, cwd=Path(repo.local_path), timeout_seconds=self._tool_specs["ExecuteTests"].timeout_seconds)
        return ToolInvocationResponse(
            tool_name="ExecuteTests",
            dry_run=False,
            success=completed["returncode"] == 0,
            execution_ms=0,
            result={"command": command, **completed},
            estimated_impact="runs tests only",
            risks=["test runtime"],
        )

    async def _execute_shell(self, payload: dict[str, Any], *, dry_run: bool, repository: RepositoryRecord | None, plan_id: str | None) -> ToolInvocationResponse:
        repo = self._require_repository(repository)
        command = payload["command"]
        args = self._validated_shell_args(command, tests_only=False)
        if dry_run:
            return ToolInvocationResponse(
                tool_name="ExecuteShell",
                dry_run=True,
                success=True,
                execution_ms=0,
                result={"command": command, "args": args, "would_run": True},
                estimated_impact="restricted shell command",
                risks=["command execution"],
            )
        completed = await self._run_shell_command(args, cwd=Path(repo.local_path), timeout_seconds=self._tool_specs["ExecuteShell"].timeout_seconds)
        return ToolInvocationResponse(
            tool_name="ExecuteShell",
            dry_run=False,
            success=completed["returncode"] == 0,
            execution_ms=0,
            result={"command": command, **completed},
            estimated_impact="restricted shell command",
            risks=["command execution"],
        )

    async def _query_vector_store(self, payload: dict[str, Any], *, dry_run: bool, repository: RepositoryRecord | None, plan_id: str | None) -> ToolInvocationResponse:
        if dry_run:
            return ToolInvocationResponse(
                tool_name="QueryVectorStore",
                dry_run=True,
                success=True,
                execution_ms=0,
                result={"query": payload["query"], "top_k": payload["top_k"], "would_run": True},
                estimated_impact="read-only vector lookup",
                risks=[],
            )
        embedding = await self.ollama.embed_text(payload["query"])
        hits = self.chroma.search(query_embedding=embedding, repository_id=payload["repository_id"], top_k=payload["top_k"])
        return ToolInvocationResponse(
            tool_name="QueryVectorStore",
            dry_run=False,
            success=True,
            execution_ms=0,
            result={"hits": hits, "query": payload["query"], "top_k": payload["top_k"]},
            affected_files=[hit.get("metadata", {}).get("path", "") for hit in hits if hit.get("metadata")],
            estimated_impact="read-only vector lookup",
            risks=[],
        )

    async def _query_postgres(self, payload: dict[str, Any], *, dry_run: bool, repository: RepositoryRecord | None, plan_id: str | None) -> ToolInvocationResponse:
        sql = payload["sql"].strip()
        if not re.match(r"^(select|with)\b", sql, flags=re.IGNORECASE):
            raise ValueError("QueryPostgres only allows read-only SELECT/WITH statements")
        if dry_run:
            return ToolInvocationResponse(
                tool_name="QueryPostgres",
                dry_run=True,
                success=True,
                execution_ms=0,
                result={"sql": sql, "parameters": payload.get("parameters", {}), "would_run": True},
                estimated_impact="read-only database query",
                risks=[],
            )
        result = await self.session.execute(text(sql), payload.get("parameters", {}))
        rows = [dict(row) for row in result.mappings().all()]
        return ToolInvocationResponse(
            tool_name="QueryPostgres",
            dry_run=False,
            success=True,
            execution_ms=0,
            result={"rows": rows, "row_count": len(rows)},
            estimated_impact="read-only database query",
            risks=[],
        )

    async def _create_checkpoint(
        self,
        repository: RepositoryRecord,
        plan_id: str | None,
        reasoning: str,
        modified_files: dict[str, Any],
    ) -> str:
        repo = await self._open_repo(repository.local_path)
        branch_name = self._current_branch_name(repo)
        git_sha = repo.head.commit.hexsha if not repo.head.is_detached else repo.head.commit.hexsha
        status = await asyncio.to_thread(lambda: repo.git.status("--short"))
        checkpoint = ExecutionCheckpoint(
            plan_id=plan_id,
            repository_id=repository.id,
            branch_name=branch_name,
            git_sha=git_sha,
            modified_files_json=sorted(set(self._parse_status_files(status) + self._collect_modified_targets(modified_files))),
            reasoning=reasoning,
            plan_json=(await self._plan_as_dict(plan_id)) if plan_id else {},
            metadata_json={"status": status},
        )
        self.session.add(checkpoint)
        await self.session.commit()
        await self.session.refresh(checkpoint)
        return checkpoint.id

    async def _plan_as_dict(self, plan_id: str | None) -> dict[str, Any]:
        if not plan_id:
            return {}
        record = await self.session.get(ActionPlanRecord, plan_id)
        return record.plan_json if record else {}

    async def _log_invocation(
        self,
        *,
        plan_id: str | None,
        checkpoint_id: str | None,
        repository_id: str | None,
        tool_name: str,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        dry_run: bool,
        success: bool,
        execution_ms: int,
        exception_message: str,
    ) -> None:
        log = ToolInvocationLog(
            plan_id=plan_id,
            checkpoint_id=checkpoint_id,
            repository_id=repository_id,
            tool_name=tool_name,
            inputs_json=inputs,
            outputs_json=outputs,
            dry_run=dry_run,
            success=success,
            execution_ms=execution_ms,
            exception_message=exception_message,
        )
        self.session.add(log)
        await self.session.commit()

    async def _mark_plan_executed(self, plan_id: str) -> None:
        record = await self.session.get(ActionPlanRecord, plan_id)
        if not record:
            return
        record.approval_status = "executed"
        await self.session.commit()

    def _build_plan(self, request: ActionPlanCreateRequest) -> ActionPlanRead:
        text_blob = " ".join([request.objective, request.request_text, " ".join(request.affected_files)]).lower()
        modifying = any(keyword in text_blob for keyword in ["write", "edit", "update", "create", "delete", "remove", "refactor", "implement", "patch", "commit", "rollback"])
        tool_names = ["ReadFile", "SearchRepository", "ListFiles", "GitStatus"]
        if modifying:
            tool_names.extend(["GitDiff", "CreateBranch", "WriteFile", "ExecuteTests", "CommitChanges", "RollbackCommit"])
        else:
            tool_names.extend(["GitDiff", "QueryVectorStore", "QueryPostgres"])
        if "test" in text_blob and "ExecuteTests" not in tool_names:
            tool_names.append("ExecuteTests")
        if "shell" in text_blob and "ExecuteShell" not in tool_names:
            tool_names.append("ExecuteShell")

        risk = "high" if any(keyword in text_blob for keyword in ["delete", "rollback", "overwrite", "migrate"] ) and modifying else "medium" if modifying else "low"
        execution_order = [
            PlanStepRead(order=1, title="Intent Analysis", description="Clarify objective and determine whether the request modifies files.", tools=[], dry_run=True),
            PlanStepRead(order=2, title="Task Breakdown", description="Identify affected repositories and files.", tools=["ReadFile", "SearchRepository", "ListFiles"], dry_run=True),
            PlanStepRead(order=3, title="Required Tools", description="Select the minimal tool set needed for the request.", tools=tool_names, dry_run=True),
            PlanStepRead(order=4, title="Execution Order", description="Preview the proposed change as a dry run before approval.", tools=[name for name in tool_names if name not in {"QueryPostgres", "QueryVectorStore"}], dry_run=True),
            PlanStepRead(order=5, title="Risk Assessment", description=f"Estimated risk: {risk}.", tools=[], dry_run=True),
            PlanStepRead(order=6, title="Approval Required", description="Modifying actions require explicit human approval.", tools=["RollbackCommit"], dry_run=True),
        ]
        return ActionPlanRead(
            plan_id=str(uuid4()),
            objective=request.objective,
            reasoning=request.reasoning or request.request_text,
            affected_repositories=[{"repository_id": repository_id} for repository_id in request.repository_ids],
            affected_files=request.affected_files,
            estimated_risk=risk,
            required_tools=tool_names,
            rollback_strategy="Capture a checkpoint, restore the saved git SHA and branch, then resync metadata, graph, and vector index.",
            approval_status="pending_approval" if modifying else "ready",
            execution_order=execution_order,
        )

    def _plan_from_record(self, record: ActionPlanRecord) -> ActionPlanRead:
        return ActionPlanRead(
            plan_id=record.id,
            objective=record.objective,
            reasoning=record.reasoning,
            affected_repositories=record.affected_repositories_json,
            affected_files=record.affected_files_json,
            estimated_risk=record.estimated_risk,
            required_tools=record.required_tools_json,
            rollback_strategy=record.rollback_strategy,
            approval_status=record.approval_status,
            execution_order=[PlanStepRead.model_validate(step) for step in record.execution_order_json],
        )

    def _checkpoint_from_record(self, record: ExecutionCheckpoint) -> CheckpointRead:
        return CheckpointRead(
            checkpoint_id=record.id,
            plan_id=record.plan_id,
            repository_id=record.repository_id,
            branch_name=record.branch_name,
            git_sha=record.git_sha,
            modified_files=record.modified_files_json,
            reasoning=record.reasoning,
            plan=record.plan_json,
            metadata=record.metadata_json,
            created_at=record.created_at,
        )

    def _build_tool_specs(self) -> dict[str, ToolSpec]:
        return {
            "ReadFile": ToolSpec("ReadFile", "Read a file from a repository.", ReadFileInput, "read", timeout_seconds=10, dry_run_supported=True),
            "WriteFile": ToolSpec("WriteFile", "Write file contents with diff preview and checkpointing.", WriteFileInput, "write", timeout_seconds=15, rollback_supported=True, dry_run_supported=True),
            "SearchRepository": ToolSpec("SearchRepository", "Search repository files by text or regex.", SearchRepositoryInput, "read", timeout_seconds=20, dry_run_supported=True),
            "ListFiles": ToolSpec("ListFiles", "List repository files.", ListFilesInput, "read", timeout_seconds=10, dry_run_supported=True),
            "GitStatus": ToolSpec("GitStatus", "Show git status.", GitStatusInput, "read", timeout_seconds=10, dry_run_supported=True),
            "GitDiff": ToolSpec("GitDiff", "Show git diffs.", GitDiffInput, "read", timeout_seconds=10, dry_run_supported=True),
            "CreateBranch": ToolSpec("CreateBranch", "Create or switch to a branch.", CreateBranchInput, "write", timeout_seconds=15, rollback_supported=True, dry_run_supported=True),
            "CommitChanges": ToolSpec("CommitChanges", "Commit repository changes.", CommitChangesInput, "write", timeout_seconds=30, rollback_supported=True, dry_run_supported=True),
            "RollbackCommit": ToolSpec("RollbackCommit", "Restore a checkpointed repository state.", RollbackCommitInput, "write", timeout_seconds=60, rollback_supported=True, dry_run_supported=True),
            "ExecuteTests": ToolSpec("ExecuteTests", "Run an approved test command.", ExecuteTestsInput, "read", timeout_seconds=300, dry_run_supported=True),
            "ExecuteShell": ToolSpec("ExecuteShell", "Run a restricted shell command.", ExecuteShellInput, "write", timeout_seconds=120, rollback_supported=True, dry_run_supported=True),
            "QueryVectorStore": ToolSpec("QueryVectorStore", "Query the repository vector store.", QueryVectorStoreInput, "read", timeout_seconds=20, dry_run_supported=True),
            "QueryPostgres": ToolSpec("QueryPostgres", "Run a read-only PostgreSQL query.", QueryPostgresInput, "read", timeout_seconds=20, dry_run_supported=True),
        }

    def _requires_checkpoint(self, spec: ToolSpec, dry_run: bool) -> bool:
        return not dry_run and spec.permission_level != "read"

    async def _plan_is_approved(self, plan_id: str | None) -> bool:
        if not plan_id:
            return False
        record = await self.session.get(ActionPlanRecord, plan_id)
        return bool(record and record.approval_status == "approved")

    async def _resolve_repository(self, repository_id: str | None) -> RepositoryRecord | None:
        if not repository_id:
            return None
        return await self.repository_service.get_repository(repository_id)

    def _require_repository(self, repository: RepositoryRecord | None) -> RepositoryRecord:
        if not repository:
            raise ValueError("Repository is required for this tool")
        return repository

    def _resolve_repo_path(self, repository: RepositoryRecord, relative_path: str) -> Path:
        root = Path(repository.local_path)
        return (root / relative_path).resolve() if relative_path else root.resolve()

    async def _open_repo(self, repository_path: str) -> Repo:
        return await asyncio.to_thread(Repo, repository_path)

    def _current_branch_name(self, repo: Repo) -> str:
        try:
            return repo.active_branch.name
        except Exception:
            return "DETACHED"

    def _restore_repository_state(self, repo: Repo, branch_name: str, git_sha: str) -> None:
        if branch_name != "DETACHED":
            repo.git.checkout(branch_name)
        repo.git.reset("--hard", git_sha)
        repo.git.clean("-fd")

    def _checkout_branch(self, repo: Repo, branch_name: str, from_ref: str | None) -> None:
        if from_ref:
            repo.git.checkout("-B", branch_name, from_ref)
        else:
            repo.git.checkout("-B", branch_name)

    def _commit_repo(self, repo: Repo, message: str) -> None:
        repo.git.add(A=True)
        repo.index.commit(message)

    def _write_text_file(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _parse_status_files(self, status_output: str) -> list[str]:
        files: list[str] = []
        for line in status_output.splitlines():
            line = line.strip()
            if not line:
                continue
            if len(line) > 3:
                path = line[3:].strip()
                if " -> " in path:
                    path = path.split(" -> ")[-1]
                files.append(path)
        return files

    def _collect_modified_targets(self, payload: dict[str, Any]) -> list[str]:
        targets: list[str] = []
        for key in ("path", "paths", "file_path"):
            value = payload.get(key)
            if isinstance(value, str):
                targets.append(value)
            elif isinstance(value, list):
                targets.extend([str(item) for item in value])
        return targets

    async def _run_shell_command(self, args: list[str], *, cwd: Path, timeout_seconds: int) -> dict[str, Any]:
        def _runner() -> dict[str, Any]:
            completed = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, shell=False, timeout=timeout_seconds)
            return {
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }

        return await asyncio.to_thread(_runner)

    def _validated_shell_args(self, command: str, *, tests_only: bool) -> list[str]:
        normalized = " ".join(shlex.split(command, posix=os.name != "nt")).lower()
        if normalized.startswith("python ") and "-m pytest" not in normalized:
            raise ValueError("Direct Python execution is not allowed")
        allowed_prefixes = [
            "git ",
            "git",
            "pytest",
            "python -m pytest",
            "uv run pytest",
            "poetry run pytest",
            "npm test",
            "npm run test",
            "pnpm test",
            "yarn test",
            "ruff",
            "mypy",
            "black",
        ]
        if tests_only:
            allowed_prefixes = [prefix for prefix in allowed_prefixes if "git" not in prefix]
        if not any(normalized.startswith(prefix) for prefix in allowed_prefixes):
            raise ValueError("Command is not allowed by the restricted shell policy")
        return shlex.split(command, posix=os.name != "nt")

# Compatibility alias for future imports.
Phase3ToolService = Phase3Service
