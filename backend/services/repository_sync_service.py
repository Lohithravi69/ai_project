from __future__ import annotations

import asyncio
from collections import Counter
from pathlib import Path
from typing import Any

from git import Repo
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import ChunkRecord, FileRecord, RepositoryRecord, ScanRun
from backend.monitoring.logging import logger
from backend.services.observability_service import ObservabilityService
from backend.services.knowledge_graph import KnowledgeGraphBuilder
from backend.services.scanner_service import ScannerService
from backend.utils.files import hash_content, iter_text_files, safe_read_text


class RepositorySyncService:
    """Incrementally synchronize repositories and re-index only changed files."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.scanner = ScannerService(session)
        self.graph = KnowledgeGraphBuilder()
        self.observability = ObservabilityService()

    async def sync_repository(self, repository_id: str, pull_remote: bool = True) -> ScanRun:
        repository = await self.session.get(RepositoryRecord, repository_id)
        if not repository:
            raise ValueError("Repository not found")

        execution_id = await self.observability.start_agent_execution(
            self.session,
            repository_id,
            agent_name="repository_sync",
            task_name="sync_repository",
            metadata={"local_path": repository.local_path, "pull_remote": pull_remote},
        )

        scan_run = ScanRun(repository_id=repository.id, status="running")
        self.session.add(scan_run)
        await self.session.commit()
        await self.session.refresh(scan_run)

        try:
            root = await self._prepare_repository_root(repository, pull_remote, execution_id)
            await self.observability.append_step(self.session, execution_id, "prepare", "ok", str(root))

            current_files: dict[str, Path] = {}
            current_hashes: dict[str, str] = {}
            for file_path in iter_text_files(root):
                text = safe_read_text(file_path, self.scanner.settings.max_file_size_bytes)
                if not text:
                    continue
                current_files[str(file_path)] = file_path
                current_hashes[str(file_path)] = hash_content(text)

            existing_result = await self.session.execute(select(FileRecord).where(FileRecord.repository_id == repository_id))
            existing_files = {file_record.path: file_record for file_record in existing_result.scalars().all()}

            if not existing_files and current_files:
                changed_paths = list(current_files.keys())
                deleted_paths: list[str] = []
            else:
                changed_paths = [path for path, file_path in current_files.items() if existing_files.get(path) is None or existing_files[path].content_hash != current_hashes[path]]
                deleted_paths = [path for path in existing_files.keys() if path not in current_files]

            await self.observability.append_step(
                self.session,
                execution_id,
                "diff",
                "ok",
                f"changed={len(changed_paths)}, deleted={len(deleted_paths)}",
            )

            deleted_count = 0
            for path in deleted_paths:
                deleted_count += await self._delete_file(repository_id, existing_files[path], execution_id, reason="deleted")

            changed_count = 0
            for path in changed_paths:
                file_path = current_files[path]
                content = safe_read_text(file_path, self.scanner.settings.max_file_size_bytes)
                if not content:
                    continue
                changed_count += await self._index_file(repository_id, file_path, content, execution_id)

            await self._refresh_repository_metadata(repository_id, repository, changed_count, deleted_count)

            await self._finalize_scan_run(scan_run, repository, changed_count, deleted_count)
            await self.observability.finish_agent_execution(self.session, execution_id, "completed")
            return scan_run
        except Exception as exc:
            repository.scan_status = "failed"
            scan_run.status = "failed"
            scan_run.error_message = str(exc)
            await self.session.commit()
            await self.observability.finish_agent_execution(self.session, execution_id, "failed", str(exc))
            raise

    async def _prepare_repository_root(self, repository: RepositoryRecord, pull_remote: bool, execution_id: str) -> Path:
        root = await self.scanner.ensure_local_repository_path(repository)
        if not pull_remote:
            return root

        try:
            await asyncio.to_thread(self._pull_repository, root)
            await self.observability.append_step(self.session, execution_id, "git_pull", "ok", "repository updated")
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(f"git pull failed for {repository.full_name}: {exc}")
            await self.observability.append_step(self.session, execution_id, "git_pull", "degraded", str(exc))
        return root

    @staticmethod
    def _pull_repository(root: Path) -> None:
        if not (root / ".git").exists():
            return
        repo = Repo(root)
        repo.remotes.origin.pull()

    async def _index_file(self, repository_id: str, file_path: Path, content: str, execution_id: str) -> int:
        parsed = self.scanner.parser.parse(file_path, content)
        await self.graph.delete_file(self.session, repository_id, file_path)
        file_record = await self.scanner._upsert_file(repository_id, file_path, parsed, content)
        await self._clear_existing_chunks(file_record)
        await self.scanner._upsert_chunks(repository_id, file_record, content)
        await self.graph.sync_file(self.session, repository_id, file_path, parsed)
        await self.observability.append_step(self.session, execution_id, "index_file", "ok", str(file_path))
        return 1

    async def _clear_existing_chunks(self, file_record: FileRecord) -> None:
        chunk_result = await self.session.execute(select(ChunkRecord).where(ChunkRecord.file_id == file_record.id))
        chunks = list(chunk_result.scalars().all())
        if not chunks:
            return
        embedding_ids = [chunk.embedding_id for chunk in chunks if chunk.embedding_id]
        self.scanner.chroma.delete_chunks(embedding_ids)
        await self.session.execute(delete(ChunkRecord).where(ChunkRecord.file_id == file_record.id))
        await self.session.commit()

    async def _delete_file(self, repository_id: str, file_record: FileRecord, execution_id: str, reason: str) -> int:
        await self.graph.delete_file(self.session, repository_id, file_record.path)
        chunk_result = await self.session.execute(select(ChunkRecord).where(ChunkRecord.file_id == file_record.id))
        chunks = list(chunk_result.scalars().all())
        embedding_ids = [chunk.embedding_id for chunk in chunks if chunk.embedding_id]
        self.scanner.chroma.delete_chunks(embedding_ids)
        await self.session.execute(delete(ChunkRecord).where(ChunkRecord.file_id == file_record.id))
        await self.session.execute(delete(FileRecord).where(FileRecord.id == file_record.id))
        await self.session.commit()
        await self.observability.append_step(self.session, execution_id, "delete_file", "ok", f"{reason}: {file_record.path}")
        return 1

    async def _refresh_repository_metadata(self, repository_id: str, repository: RepositoryRecord, changed_count: int, deleted_count: int) -> None:
        files_result = await self.session.execute(select(FileRecord).where(FileRecord.repository_id == repository_id))
        files = list(files_result.scalars().all())
        language_counter: Counter[str] = Counter()
        summary_lines: list[str] = []
        framework_hints: Counter[str] = Counter(repository.framework_summary or {})

        for file_record in files:
            language_counter[file_record.language] += 1
            summary_lines.append(f"{file_record.path}: {file_record.summary}")

        root = Path(repository.local_path)
        for file_path in iter_text_files(root):
            content = safe_read_text(file_path, self.scanner.settings.max_file_size_bytes)
            if content:
                for hint in self.scanner._detect_framework_hints(file_path, content):
                    framework_hints[hint] += 1

        repository.scan_status = "synced" if changed_count or deleted_count else "ready"
        repository.language_summary = dict(language_counter)
        repository.framework_summary = dict(framework_hints)
        repository.summary = self.scanner._build_project_summary(repository.full_name, summary_lines)
        await self.session.commit()

    async def _finalize_scan_run(self, scan_run: ScanRun, repository: RepositoryRecord, changed_count: int, deleted_count: int) -> None:
        stats_result = await self.session.execute(select(FileRecord).where(FileRecord.repository_id == repository.id))
        files = list(stats_result.scalars().all())
        scan_run.status = "completed"
        scan_run.file_count = len(files)
        scan_run.function_count = sum(len(file.symbols_json.get("functions", [])) for file in files)
        scan_run.class_count = sum(len(file.symbols_json.get("classes", [])) for file in files)
        scan_run.route_count = sum(len(file.symbols_json.get("routes", [])) for file in files)
        await self.session.commit()
