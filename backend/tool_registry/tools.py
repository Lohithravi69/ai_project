from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import shutil
import subprocess
import time
from difflib import unified_diff
from pathlib import Path
from typing import Any
from uuid import uuid4

from git import Repo
from pydantic import BaseModel, Field

from backend.tool_registry.base import BaseTool, ToolRunResult, ToolSpec
from backend.utils.files import hash_content, iter_text_files, safe_read_text


# ── Input Models ───────────────────────────────────────────────────────────────


class PathInput(BaseModel):
    repository_id: str
    path: str
    dry_run: bool = True


class ReadFileInput(PathInput):
    pass


class WriteFileInput(PathInput):
    content: str = Field(min_length=0)


class CreateFileInput(PathInput):
    content: str = Field(default="")


class DeleteFileInput(PathInput):
    pass


class MoveFileInput(PathInput):
    destination: str = Field(min_length=1)


class SearchRepositoryInput(BaseModel):
    repository_id: str
    query: str
    regex: bool = False
    case_sensitive: bool = False
    path_prefix: str | None = None
    dry_run: bool = True


class ListFilesInput(BaseModel):
    repository_id: str
    path: str | None = None
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
    branch_name: str = Field(min_length=1)
    from_ref: str | None = None
    dry_run: bool = True


class CheckoutBranchInput(BaseModel):
    repository_id: str
    branch_name: str = Field(min_length=1)
    create_if_missing: bool = False
    dry_run: bool = True


class CommitChangesInput(BaseModel):
    repository_id: str
    message: str = Field(min_length=1)
    dry_run: bool = True


class RollbackCommitInput(BaseModel):
    repository_id: str
    checkpoint_id: str
    dry_run: bool = True


class RunPyTestInput(BaseModel):
    repository_id: str
    test_path: str | None = None
    options: str = ""
    dry_run: bool = True


class RunPlaywrightInput(BaseModel):
    repository_id: str
    test_path: str | None = None
    options: str = ""
    dry_run: bool = True


class RunShellRestrictedInput(BaseModel):
    repository_id: str
    command: str = Field(min_length=1)
    dry_run: bool = True


class FormatCodeInput(BaseModel):
    repository_id: str
    path: str | None = None
    tool: str = "ruff"
    dry_run: bool = True


class QueryVectorStoreInput(BaseModel):
    repository_id: str
    query: str
    top_k: int = 5
    dry_run: bool = True


class QueryPostgresInput(BaseModel):
    sql: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = True


class ReadLogsInput(BaseModel):
    repository_id: str
    lines: int = 50
    service: str | None = None
    dry_run: bool = True


class RestartContainerInput(BaseModel):
    repository_id: str
    container_name: str
    dry_run: bool = True


# ── Tool Implementations ───────────────────────────────────────────────────────


def _resolve_local_path(repository_id: str) -> str:
    from backend.config import get_settings
    from backend.database.session import async_session_maker
    from backend.database.models import RepositoryRecord

    settings = get_settings()
    # Fallback: construct path from repositories_root
    return str(Path(settings.repositories_root) / repository_id)


async def _get_repo_path(repository_id: str) -> str:
    try:
        from sqlalchemy import select

        from backend.database.models import RepositoryRecord
        from backend.database.session import async_session_maker

        async with async_session_maker() as session:
            result = await session.execute(select(RepositoryRecord).where(RepositoryRecord.id == repository_id))
            record = result.scalar_one_or_none()
            if record and record.local_path:
                return record.local_path
    except Exception:
        pass
    return _resolve_local_path(repository_id)


# ── ReadFile ───────────────────────────────────────────────────────────────────


class ReadFileTool(BaseTool):
    def _build_spec(self) -> ToolSpec:
        return ToolSpec(
            name="ReadFile",
            description="Read a file from a repository.",
            permission_level="read",
            timeout_seconds=10,
            dry_run_support=True,
            input_schema_json=ReadFileInput.model_json_schema(),
            output_schema_json={"type": "object", "properties": {"content": {"type": "string"}, "metadata": {"type": "object"}}},
        )

    def _input_model(self) -> type[BaseModel]:
        return ReadFileInput

    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        return ToolRunResult(success=True, result={"path": payload["path"], "would_read": True}, affected_files=[payload["path"]], estimated_impact="read-only")

    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        repo_path = await _get_repo_path(payload["repository_id"])
        full_path = Path(repo_path) / payload["path"]
        if not full_path.exists():
            return ToolRunResult(success=False, exception_message=f"File not found: {payload['path']}")
        content = safe_read_text(full_path)
        metadata = {
            "path": str(full_path.relative_to(Path(repo_path))),
            "size_bytes": full_path.stat().st_size,
            "hash": hash_content(content or ""),
        }
        return ToolRunResult(
            success=True,
            result={"content": content or "", "metadata": metadata},
            affected_files=[payload["path"]],
            estimated_impact="read-only",
        )


# ── WriteFile ──────────────────────────────────────────────────────────────────


class WriteFileTool(BaseTool):
    def _build_spec(self) -> ToolSpec:
        return ToolSpec(
            name="WriteFile",
            description="Write file contents with diff preview and checkpointing.",
            permission_level="write",
            timeout_seconds=15,
            rollback_support=True,
            dry_run_support=True,
            input_schema_json=WriteFileInput.model_json_schema(),
            output_schema_json={"type": "object", "properties": {"path": {"type": "string"}, "written": {"type": "boolean"}}},
        )

    def _input_model(self) -> type[BaseModel]:
        return WriteFileInput

    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        repo_path = await _get_repo_path(payload["repository_id"])
        full_path = Path(repo_path) / payload["path"]
        existing = ""
        if full_path.exists():
            existing = safe_read_text(full_path, max_bytes=10_000_000) or ""
        diff = "\n".join(
            unified_diff(
                existing.splitlines(),
                payload["content"].splitlines(),
                fromfile=str(full_path),
                tofile=f"{full_path} (proposed)",
                lineterm="",
            )
        )
        return ToolRunResult(
            success=True,
            result={"path": payload["path"], "would_write": True},
            affected_files=[payload["path"]],
            diff_preview=diff,
            estimated_impact="modifies one file",
            risks=["content overwrite"],
        )

    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        repo_path = await _get_repo_path(payload["repository_id"])
        full_path = Path(repo_path) / payload["path"]
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(payload["content"], encoding="utf-8")
        return ToolRunResult(
            success=True,
            result={"path": str(full_path), "written": True, "content_hash": hash_content(payload["content"])},
            affected_files=[payload["path"]],
            estimated_impact="modifies one file",
            risks=["content overwrite"],
        )


# ── CreateFile ─────────────────────────────────────────────────────────────────


class CreateFileTool(BaseTool):
    def _build_spec(self) -> ToolSpec:
        return ToolSpec(
            name="CreateFile",
            description="Create a new file in the repository.",
            permission_level="write",
            timeout_seconds=10,
            rollback_support=True,
            dry_run_support=True,
            input_schema_json=CreateFileInput.model_json_schema(),
            output_schema_json={"type": "object", "properties": {"path": {"type": "string"}, "created": {"type": "boolean"}}},
        )

    def _input_model(self) -> type[BaseModel]:
        return CreateFileInput

    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        repo_path = await _get_repo_path(payload["repository_id"])
        full_path = Path(repo_path) / payload["path"]
        if full_path.exists():
            return ToolRunResult(success=False, exception_message=f"File already exists: {payload['path']}")
        return ToolRunResult(success=True, result={"path": payload["path"], "would_create": True}, affected_files=[payload["path"]], estimated_impact="creates one file")

    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        repo_path = await _get_repo_path(payload["repository_id"])
        full_path = Path(repo_path) / payload["path"]
        if full_path.exists():
            return ToolRunResult(success=False, exception_message=f"File already exists: {payload['path']}")
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(payload.get("content", ""), encoding="utf-8")
        return ToolRunResult(success=True, result={"path": str(full_path), "created": True}, affected_files=[payload["path"]], estimated_impact="creates one file")


# ── DeleteFile ─────────────────────────────────────────────────────────────────


class DeleteFileTool(BaseTool):
    def _build_spec(self) -> ToolSpec:
        return ToolSpec(
            name="DeleteFile",
            description="Delete a file from the repository.",
            permission_level="write",
            timeout_seconds=10,
            rollback_support=True,
            dry_run_support=True,
            input_schema_json=DeleteFileInput.model_json_schema(),
            output_schema_json={"type": "object", "properties": {"path": {"type": "string"}, "deleted": {"type": "boolean"}}},
        )

    def _input_model(self) -> type[BaseModel]:
        return DeleteFileInput

    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        repo_path = await _get_repo_path(payload["repository_id"])
        full_path = Path(repo_path) / payload["path"]
        if not full_path.exists():
            return ToolRunResult(success=False, exception_message=f"File not found: {payload['path']}")
        return ToolRunResult(
            success=True,
            result={"path": payload["path"], "would_delete": True},
            affected_files=[payload["path"]],
            estimated_impact="deletes one file",
            risks=["data loss"],
        )

    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        repo_path = await _get_repo_path(payload["repository_id"])
        full_path = Path(repo_path) / payload["path"]
        if not full_path.exists():
            return ToolRunResult(success=False, exception_message=f"File not found: {payload['path']}")
        full_path.unlink()
        return ToolRunResult(success=True, result={"path": str(full_path), "deleted": True}, affected_files=[payload["path"]], estimated_impact="deletes one file", risks=["data loss"])


# ── MoveFile ───────────────────────────────────────────────────────────────────


class MoveFileTool(BaseTool):
    def _build_spec(self) -> ToolSpec:
        return ToolSpec(
            name="MoveFile",
            description="Move or rename a file within the repository.",
            permission_level="write",
            timeout_seconds=10,
            rollback_support=True,
            dry_run_support=True,
            input_schema_json=MoveFileInput.model_json_schema(),
            output_schema_json={"type": "object", "properties": {"source": {"type": "string"}, "destination": {"type": "string"}, "moved": {"type": "boolean"}}},
        )

    def _input_model(self) -> type[BaseModel]:
        return MoveFileInput

    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        repo_path = await _get_repo_path(payload["repository_id"])
        source = Path(repo_path) / payload["path"]
        dest = Path(repo_path) / payload["destination"]
        if not source.exists():
            return ToolRunResult(success=False, exception_message=f"Source not found: {payload['path']}")
        if dest.exists():
            return ToolRunResult(success=False, exception_message=f"Destination already exists: {payload['destination']}")
        return ToolRunResult(
            success=True,
            result={"source": payload["path"], "destination": payload["destination"], "would_move": True},
            affected_files=[payload["path"], payload["destination"]],
            estimated_impact="moves one file",
        )

    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        repo_path = await _get_repo_path(payload["repository_id"])
        source = Path(repo_path) / payload["path"]
        dest = Path(repo_path) / payload["destination"]
        if not source.exists():
            return ToolRunResult(success=False, exception_message=f"Source not found: {payload['path']}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(dest))
        return ToolRunResult(
            success=True,
            result={"source": str(source), "destination": str(dest), "moved": True},
            affected_files=[payload["path"], payload["destination"]],
            estimated_impact="moves one file",
        )


# ── SearchRepository ──────────────────────────────────────────────────────────


class SearchRepositoryTool(BaseTool):
    def _build_spec(self) -> ToolSpec:
        return ToolSpec(
            name="SearchRepository",
            description="Search repository files by text or regex.",
            permission_level="read",
            timeout_seconds=20,
            dry_run_support=True,
            input_schema_json=SearchRepositoryInput.model_json_schema(),
            output_schema_json={"type": "object", "properties": {"matches": {"type": "array"}, "match_count": {"type": "integer"}}},
        )

    def _input_model(self) -> type[BaseModel]:
        return SearchRepositoryInput

    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        return ToolRunResult(success=True, result={"query": payload["query"], "would_search": True}, estimated_impact="read-only search")

    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        repo_path = await _get_repo_path(payload["repository_id"])
        root = Path(repo_path)
        pattern = payload["query"] if payload.get("regex") else re.escape(payload["query"])
        flags = 0 if payload.get("case_sensitive") else re.IGNORECASE
        compiled = re.compile(pattern, flags)
        matches: list[dict[str, Any]] = []
        for file_path in iter_text_files(root):
            if payload.get("path_prefix") and not str(file_path).startswith(str(root / payload["path_prefix"])):
                continue
            text_content = safe_read_text(file_path)
            if not text_content:
                continue
            for line_number, line in enumerate(text_content.splitlines(), start=1):
                if compiled.search(line):
                    matches.append({"path": str(file_path.relative_to(root)), "line": line_number, "text": line.strip()})
                    if len(matches) >= 50:
                        break
            if len(matches) >= 50:
                break
        return ToolRunResult(success=True, result={"matches": matches, "match_count": len(matches)}, affected_files=[m["path"] for m in matches], estimated_impact="read-only search")


# ── ListFiles ──────────────────────────────────────────────────────────────────


class ListFilesTool(BaseTool):
    def _build_spec(self) -> ToolSpec:
        return ToolSpec(
            name="ListFiles",
            description="List repository files.",
            permission_level="read",
            timeout_seconds=10,
            dry_run_support=True,
            input_schema_json=ListFilesInput.model_json_schema(),
            output_schema_json={"type": "object", "properties": {"files": {"type": "array"}}},
        )

    def _input_model(self) -> type[BaseModel]:
        return ListFilesInput

    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        return ToolRunResult(success=True, result={"would_list": True}, estimated_impact="read-only listing")

    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        repo_path = await _get_repo_path(payload["repository_id"])
        root = Path(repo_path)
        base = (root / payload["path"]).resolve() if payload.get("path") else root
        files: list[str] = []
        for fp in base.rglob("*"):
            if fp.is_file():
                try:
                    files.append(str(fp.relative_to(root)))
                except ValueError:
                    files.append(str(fp))
        return ToolRunResult(success=True, result={"files": sorted(files)}, estimated_impact="read-only listing")


# ── GitStatus ──────────────────────────────────────────────────────────────────


class GitStatusTool(BaseTool):
    def _build_spec(self) -> ToolSpec:
        return ToolSpec(
            name="GitStatus",
            description="Show git status.",
            permission_level="read",
            timeout_seconds=10,
            dry_run_support=True,
            input_schema_json=GitStatusInput.model_json_schema(),
            output_schema_json={"type": "object", "properties": {"status": {"type": "string"}}},
        )

    def _input_model(self) -> type[BaseModel]:
        return GitStatusInput

    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        return ToolRunResult(success=True, result={"would_show_status": True}, estimated_impact="read-only git metadata")

    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        repo_path = await _get_repo_path(payload["repository_id"])
        repo = Repo(repo_path)
        status = repo.git.status("--short")
        files = []
        for line in status.splitlines():
            line = line.strip()
            if len(line) > 3:
                path = line[3:].strip()
                if " -> " in path:
                    path = path.split(" -> ")[-1]
                files.append(path)
        return ToolRunResult(success=True, result={"status": status}, affected_files=files, estimated_impact="read-only git metadata")


# ── GitDiff ────────────────────────────────────────────────────────────────────


class GitDiffTool(BaseTool):
    def _build_spec(self) -> ToolSpec:
        return ToolSpec(
            name="GitDiff",
            description="Show git diffs.",
            permission_level="read",
            timeout_seconds=10,
            dry_run_support=True,
            input_schema_json=GitDiffInput.model_json_schema(),
            output_schema_json={"type": "object", "properties": {"diff": {"type": "string"}}},
        )

    def _input_model(self) -> type[BaseModel]:
        return GitDiffInput

    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        return ToolRunResult(success=True, result={"would_show_diff": True}, estimated_impact="read-only diff")

    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        repo_path = await _get_repo_path(payload["repository_id"])
        repo = Repo(repo_path)

        def _diff() -> str:
            if payload.get("ref_a") and payload.get("ref_b"):
                args = [payload["ref_a"], payload["ref_b"]]
                if payload.get("path"):
                    args.extend(["--", payload["path"]])
                return repo.git.diff(*args)
            if payload.get("ref_a"):
                args = [payload["ref_a"]]
                if payload.get("path"):
                    args.extend(["--", payload["path"]])
                return repo.git.diff(*args)
            return repo.git.diff()

        diff = await asyncio.to_thread(_diff)
        return ToolRunResult(
            success=True,
            result={"diff": diff},
            affected_files=[payload["path"]] if payload.get("path") else [],
            diff_preview=diff,
            estimated_impact="read-only diff",
        )


# ── CreateBranch ──────────────────────────────────────────────────────────────


class CreateBranchTool(BaseTool):
    def _build_spec(self) -> ToolSpec:
        return ToolSpec(
            name="CreateBranch",
            description="Create a new branch.",
            permission_level="write",
            timeout_seconds=15,
            rollback_support=True,
            dry_run_support=True,
            input_schema_json=CreateBranchInput.model_json_schema(),
            output_schema_json={"type": "object", "properties": {"branch_name": {"type": "string"}, "from_ref": {"type": "string"}}},
        )

    def _input_model(self) -> type[BaseModel]:
        return CreateBranchInput

    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        return ToolRunResult(
            success=True,
            result={"branch_name": payload["branch_name"], "from_ref": payload.get("from_ref"), "would_create": True},
            estimated_impact="changes repository branch pointer",
            risks=["branch switch"],
        )

    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        repo_path = await _get_repo_path(payload["repository_id"])
        repo = Repo(repo_path)
        if payload.get("from_ref"):
            repo.git.checkout("-B", payload["branch_name"], payload["from_ref"])
        else:
            repo.git.checkout("-B", payload["branch_name"])
        return ToolRunResult(
            success=True,
            result={"branch_name": payload["branch_name"], "from_ref": payload.get("from_ref"), "current_branch": payload["branch_name"]},
            estimated_impact="changes repository branch pointer",
            risks=["branch switch"],
        )


# ── CheckoutBranch ─────────────────────────────────────────────────────────────


class CheckoutBranchTool(BaseTool):
    def _build_spec(self) -> ToolSpec:
        return ToolSpec(
            name="CheckoutBranch",
            description="Checkout an existing branch or create and switch.",
            permission_level="write",
            timeout_seconds=15,
            rollback_support=True,
            dry_run_support=True,
            input_schema_json=CheckoutBranchInput.model_json_schema(),
            output_schema_json={"type": "object", "properties": {"branch_name": {"type": "string"}, "previous_branch": {"type": "string"}}},
        )

    def _input_model(self) -> type[BaseModel]:
        return CheckoutBranchInput

    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        return ToolRunResult(
            success=True,
            result={"branch_name": payload["branch_name"], "would_checkout": True},
            estimated_impact="switches branch",
            risks=["branch switch"],
        )

    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        repo_path = await _get_repo_path(payload["repository_id"])
        repo = Repo(repo_path)
        prev = None
        try:
            prev = repo.active_branch.name
        except Exception:
            prev = "DETACHED"
        try:
            repo.git.checkout(payload["branch_name"])
        except Exception:
            if payload.get("create_if_missing"):
                repo.git.checkout("-b", payload["branch_name"])
            else:
                return ToolRunResult(success=False, exception_message=f"Branch not found: {payload['branch_name']}")
        return ToolRunResult(success=True, result={"branch_name": payload["branch_name"], "previous_branch": prev}, estimated_impact="switches branch", risks=["branch switch"])


# ── CommitChanges ─────────────────────────────────────────────────────────────


class CommitChangesTool(BaseTool):
    def _build_spec(self) -> ToolSpec:
        return ToolSpec(
            name="CommitChanges",
            description="Commit repository changes.",
            permission_level="write",
            timeout_seconds=30,
            rollback_support=True,
            dry_run_support=True,
            input_schema_json=CommitChangesInput.model_json_schema(),
            output_schema_json={"type": "object", "properties": {"message": {"type": "string"}, "commit_sha": {"type": "string"}}},
        )

    def _input_model(self) -> type[BaseModel]:
        return CommitChangesInput

    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        return ToolRunResult(
            success=True,
            result={"message": payload["message"], "would_commit": True},
            estimated_impact="writes git history",
            risks=["commit history change"],
        )

    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        repo_path = await _get_repo_path(payload["repository_id"])
        repo = Repo(repo_path)
        repo.git.add(A=True)
        repo.index.commit(payload["message"])
        head_sha = repo.head.commit.hexsha
        return ToolRunResult(success=True, result={"message": payload["message"], "commit_sha": head_sha}, estimated_impact="writes git history", risks=["commit history change"])


# ── RollbackCommit ────────────────────────────────────────────────────────────


class RollbackCommitTool(BaseTool):
    def _build_spec(self) -> ToolSpec:
        return ToolSpec(
            name="RollbackCommit",
            description="Restore a checkpointed repository state.",
            permission_level="write",
            timeout_seconds=60,
            rollback_support=True,
            dry_run_support=True,
            input_schema_json=RollbackCommitInput.model_json_schema(),
            output_schema_json={"type": "object", "properties": {"checkpoint_id": {"type": "string"}, "restored": {"type": "boolean"}}},
        )

    def _input_model(self) -> type[BaseModel]:
        return RollbackCommitInput

    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        return ToolRunResult(success=True, result={"checkpoint_id": payload["checkpoint_id"], "would_restore": True}, estimated_impact="restores repository state", risks=["state restoration"])

    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        from backend.execution.checkpoint_engine import CheckpointEngine
        from backend.execution.rollback_engine import RollbackEngine
        from backend.database.session import async_session_maker

        async with async_session_maker() as session:
            engine = RollbackEngine(session)
            result = await engine.rollback(payload["checkpoint_id"], dry_run=False)
            return ToolRunResult(
                success=result.success,
                result={"checkpoint_id": payload["checkpoint_id"], "restored": result.success, "summary": result.summary},
                estimated_impact="restores repository state and indexes",
                risks=["state restoration"],
            )


# ── RunPyTest ──────────────────────────────────────────────────────────────────


class RunPyTestTool(BaseTool):
    def _build_spec(self) -> ToolSpec:
        return ToolSpec(
            name="RunPyTest",
            description="Run pytest on the repository.",
            permission_level="read",
            timeout_seconds=300,
            dry_run_support=True,
            input_schema_json=RunPyTestInput.model_json_schema(),
            output_schema_json={"type": "object", "properties": {"returncode": {"type": "integer"}, "stdout": {"type": "string"}, "stderr": {"type": "string"}}},
        )

    def _input_model(self) -> type[BaseModel]:
        return RunPyTestInput

    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        return ToolRunResult(success=True, result={"would_run": True, "command": "pytest"}, estimated_impact="runs tests only", risks=["test runtime"])

    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        repo_path = await _get_repo_path(payload["repository_id"])
        cmd = ["python", "-m", "pytest"]
        if payload.get("test_path"):
            cmd.append(payload["test_path"])
        if payload.get("options"):
            cmd.extend(shlex.split(payload["options"]))
        completed = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True, timeout=300)
        success = completed.returncode == 0
        return ToolRunResult(
            success=success,
            result={"command": " ".join(cmd), "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr},
            estimated_impact="runs tests only",
            risks=["test runtime"],
        )


# ── RunPlaywright ─────────────────────────────────────────────────────────────


class RunPlaywrightTool(BaseTool):
    def _build_spec(self) -> ToolSpec:
        return ToolSpec(
            name="RunPlaywright",
            description="Run Playwright tests on the repository.",
            permission_level="read",
            timeout_seconds=300,
            dry_run_support=True,
            input_schema_json=RunPlaywrightInput.model_json_schema(),
            output_schema_json={"type": "object", "properties": {"returncode": {"type": "integer"}, "stdout": {"type": "string"}, "stderr": {"type": "string"}}},
        )

    def _input_model(self) -> type[BaseModel]:
        return RunPlaywrightInput

    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        return ToolRunResult(success=True, result={"would_run": True, "command": "playwright"}, estimated_impact="runs browser tests", risks=["test runtime"])

    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        repo_path = await _get_repo_path(payload["repository_id"])
        cmd = ["npx", "playwright", "test"]
        if payload.get("test_path"):
            cmd.append(payload["test_path"])
        if payload.get("options"):
            cmd.extend(shlex.split(payload["options"]))
        completed = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True, timeout=300)
        success = completed.returncode == 0
        return ToolRunResult(
            success=success,
            result={"command": " ".join(cmd), "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr},
            estimated_impact="runs browser tests",
            risks=["test runtime"],
        )


# ── RunShellRestricted ─────────────────────────────────────────────────────────


ALLOWED_SHELL_PREFIXES = [
    "git ", "git",
    "pytest", "python -m pytest", "uv run pytest", "poetry run pytest",
    "npm test", "npm run test", "pnpm test", "yarn test",
    "ruff", "mypy", "black",
]


class RunShellRestrictedTool(BaseTool):
    def _build_spec(self) -> ToolSpec:
        return ToolSpec(
            name="RunShellRestricted",
            description="Run a restricted shell command (allow-list enforced).",
            permission_level="write",
            timeout_seconds=120,
            rollback_support=True,
            dry_run_support=True,
            input_schema_json=RunShellRestrictedInput.model_json_schema(),
            output_schema_json={"type": "object", "properties": {"returncode": {"type": "integer"}, "stdout": {"type": "string"}, "stderr": {"type": "string"}}},
        )

    def _input_model(self) -> type[BaseModel]:
        return RunShellRestrictedInput

    def _validate_command(self, command: str) -> list[str]:
        normalized = " ".join(shlex.split(command, posix=os.name != "nt")).lower()
        if not any(normalized.startswith(prefix) for prefix in ALLOWED_SHELL_PREFIXES):
            raise ValueError(f"Command is not allowed by the restricted shell policy: {command}")
        return shlex.split(command, posix=os.name != "nt")

    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        try:
            self._validate_command(payload["command"])
        except ValueError as exc:
            return ToolRunResult(success=False, exception_message=str(exc))
        return ToolRunResult(success=True, result={"command": payload["command"], "would_run": True}, estimated_impact="restricted shell command", risks=["command execution"])

    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        try:
            args = self._validate_command(payload["command"])
        except ValueError as exc:
            return ToolRunResult(success=False, exception_message=str(exc))
        repo_path = await _get_repo_path(payload["repository_id"])
        completed = subprocess.run(args, cwd=repo_path, capture_output=True, text=True, timeout=120, shell=False)
        success = completed.returncode == 0
        return ToolRunResult(
            success=success,
            result={"command": payload["command"], "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr},
            estimated_impact="restricted shell command",
            risks=["command execution"],
        )


# ── FormatCode ─────────────────────────────────────────────────────────────────


class FormatCodeTool(BaseTool):
    def _build_spec(self) -> ToolSpec:
        return ToolSpec(
            name="FormatCode",
            description="Format code using ruff, black, or other formatters.",
            permission_level="write",
            timeout_seconds=60,
            dry_run_support=True,
            input_schema_json=FormatCodeInput.model_json_schema(),
            output_schema_json={"type": "object", "properties": {"formatted": {"type": "boolean"}, "stdout": {"type": "string"}}},
        )

    def _input_model(self) -> type[BaseModel]:
        return FormatCodeInput

    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        return ToolRunResult(success=True, result={"tool": payload.get("tool", "ruff"), "would_format": True}, estimated_impact="formats code", risks=["code formatting changes"])

    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        repo_path = await _get_repo_path(payload["repository_id"])
        tool = payload.get("tool", "ruff")
        cmd = [tool]
        if payload.get("path"):
            cmd.append(payload["path"])
        else:
            cmd.append(".")
        completed = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True, timeout=60)
        return ToolRunResult(
            success=completed.returncode == 0,
            result={"tool": tool, "formatted": completed.returncode == 0, "stdout": completed.stdout, "stderr": completed.stderr},
            affected_files=[payload["path"]] if payload.get("path") else [],
            estimated_impact="formats code",
            risks=["code formatting changes"],
        )


# ── QueryVectorStore ──────────────────────────────────────────────────────────


class QueryVectorStoreTool(BaseTool):
    def _build_spec(self) -> ToolSpec:
        return ToolSpec(
            name="QueryVectorStore",
            description="Query the repository vector store.",
            permission_level="read",
            timeout_seconds=20,
            dry_run_support=True,
            input_schema_json=QueryVectorStoreInput.model_json_schema(),
            output_schema_json={"type": "object", "properties": {"hits": {"type": "array"}, "query": {"type": "string"}}},
        )

    def _input_model(self) -> type[BaseModel]:
        return QueryVectorStoreInput

    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        return ToolRunResult(success=True, result={"query": payload["query"], "top_k": payload["top_k"], "would_run": True}, estimated_impact="read-only vector lookup")

    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        from backend.config import get_settings
        from backend.embeddings.chroma_service import ChromaService
        from backend.embeddings.ollama_client import OllamaClient

        settings = get_settings()
        ollama = OllamaClient(settings.ollama_base_url, settings.ollama_chat_model, settings.ollama_embed_model)
        chroma = ChromaService(settings.chroma_persist_directory)
        embedding = await ollama.embed_text(payload["query"])
        hits = chroma.search(query_embedding=embedding, repository_id=payload["repository_id"], top_k=payload["top_k"])
        affected = [hit.get("metadata", {}).get("path", "") for hit in hits if hit.get("metadata")]
        return ToolRunResult(
            success=True,
            result={"hits": hits, "query": payload["query"], "top_k": payload["top_k"]},
            affected_files=affected,
            estimated_impact="read-only vector lookup",
        )


# ── QueryPostgres ──────────────────────────────────────────────────────────────


class QueryPostgresTool(BaseTool):
    def _build_spec(self) -> ToolSpec:
        return ToolSpec(
            name="QueryPostgres",
            description="Run a read-only SQL query against Postgres.",
            permission_level="read",
            timeout_seconds=20,
            dry_run_support=True,
            input_schema_json=QueryPostgresInput.model_json_schema(),
            output_schema_json={"type": "object", "properties": {"rows": {"type": "array"}, "row_count": {"type": "integer"}}},
        )

    def _input_model(self) -> type[BaseModel]:
        return QueryPostgresInput

    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        return ToolRunResult(success=True, result={"sql": payload["sql"], "would_run": True}, estimated_impact="read-only database query")

    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        from sqlalchemy import text

        from backend.database.session import async_session_maker

        sql = payload["sql"].strip()
        if not re.match(r"^(select|with)\b", sql, flags=re.IGNORECASE):
            return ToolRunResult(success=False, exception_message="Only read-only SELECT/WITH statements are allowed")
        async with async_session_maker() as session:
            result = await session.execute(text(sql), payload.get("parameters", {}))
            rows = [dict(row) for row in result.mappings().all()]
            return ToolRunResult(success=True, result={"rows": rows, "row_count": len(rows)}, estimated_impact="read-only database query")


# ── ReadLogs ───────────────────────────────────────────────────────────────────


class ReadLogsTool(BaseTool):
    def _build_spec(self) -> ToolSpec:
        return ToolSpec(
            name="ReadLogs",
            description="Read application or service logs.",
            permission_level="read",
            timeout_seconds=30,
            dry_run_support=True,
            input_schema_json=ReadLogsInput.model_json_schema(),
            output_schema_json={"type": "object", "properties": {"logs": {"type": "string"}, "lines": {"type": "integer"}}},
        )

    def _input_model(self) -> type[BaseModel]:
        return ReadLogsInput

    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        return ToolRunResult(success=True, result={"would_read_logs": True, "lines": payload.get("lines", 50)}, estimated_impact="read-only logs")

    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        repo_path = await _get_repo_path(payload["repository_id"])
        log_dir = Path(repo_path) / "logs"
        logs = ""
        if log_dir.exists():
            log_files = sorted(log_dir.glob("*.log"), key=os.path.getmtime, reverse=True)
            if log_files:
                log_content = safe_read_text(log_files[0]) or ""
                lines = log_content.splitlines()
                n = payload.get("lines", 50)
                logs = "\n".join(lines[-n:])
        return ToolRunResult(success=True, result={"logs": logs, "lines": len(logs.splitlines()) if logs else 0}, estimated_impact="read-only logs")


# ── RestartContainer ──────────────────────────────────────────────────────────


class RestartContainerTool(BaseTool):
    def _build_spec(self) -> ToolSpec:
        return ToolSpec(
            name="RestartContainer",
            description="Restart a Docker container.",
            permission_level="write",
            timeout_seconds=60,
            rollback_support=False,
            dry_run_support=True,
            input_schema_json=RestartContainerInput.model_json_schema(),
            output_schema_json={"type": "object", "properties": {"container": {"type": "string"}, "restarted": {"type": "boolean"}}},
        )

    def _input_model(self) -> type[BaseModel]:
        return RestartContainerInput

    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        return ToolRunResult(success=True, result={"container_name": payload["container_name"], "would_restart": True}, estimated_impact="restarts container", risks=["service disruption"])

    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        completed = subprocess.run(["docker", "restart", payload["container_name"]], capture_output=True, text=True, timeout=60)
        success = completed.returncode == 0
        return ToolRunResult(
            success=success,
            result={"container": payload["container_name"], "restarted": success, "stdout": completed.stdout, "stderr": completed.stderr},
            estimated_impact="restarts container",
            risks=["service disruption"],
        )


# ── Registry Export ────────────────────────────────────────────────────────────

ALL_TOOLS: list[type[BaseTool]] = [
    ReadFileTool,
    WriteFileTool,
    CreateFileTool,
    DeleteFileTool,
    MoveFileTool,
    SearchRepositoryTool,
    ListFilesTool,
    GitStatusTool,
    GitDiffTool,
    CreateBranchTool,
    CheckoutBranchTool,
    CommitChangesTool,
    RollbackCommitTool,
    RunPyTestTool,
    RunPlaywrightTool,
    RunShellRestrictedTool,
    FormatCodeTool,
    QueryVectorStoreTool,
    QueryPostgresTool,
    ReadLogsTool,
    RestartContainerTool,
]
