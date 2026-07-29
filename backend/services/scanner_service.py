from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database.models import ChunkRecord, FileRecord, RepositoryRecord, ScanRun
from backend.embeddings.chroma_service import ChromaService
from backend.embeddings.ollama_client import OllamaClient
from backend.parsers.tree_sitter_parser import ParsedFile, TreeSitterParser
from backend.services.chunking import AdvancedChunker
from backend.utils.files import hash_content, iter_text_files, safe_read_text
from backend.utils.repository import repository_local_path


class ScannerService:
    """Scan repositories, extract symbols, and push chunks into vector memory."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()
        self.parser = TreeSitterParser()
        self.chunker = AdvancedChunker()
        self.ollama = OllamaClient(self.settings.ollama_base_url, self.settings.ollama_chat_model, self.settings.ollama_embed_model)
        self.chroma = ChromaService(self.settings.chroma_persist_directory)

    async def ensure_local_repository_path(self, repository: RepositoryRecord) -> Path:
        path = repository_local_path(self.settings.repositories_root, repository.full_name)
        path.mkdir(parents=True, exist_ok=True)
        repository.local_path = str(path)
        await self.session.commit()
        return path

    async def scan_repository(self, repository_id: str) -> ScanRun:
        repository = await self.session.get(RepositoryRecord, repository_id)
        if not repository:
            raise ValueError("Repository not found")

        await self.ensure_local_repository_path(repository)
        repository.scan_status = "scanning"
        await self.session.commit()

        scan_run = ScanRun(repository_id=repository.id, status="running")
        self.session.add(scan_run)
        await self.session.commit()
        await self.session.refresh(scan_run)

        try:
            file_counter = 0
            function_counter = 0
            class_counter = 0
            route_counter = 0
            language_counter: Counter[str] = Counter()
            framework_hints: Counter[str] = Counter()
            collected_summary_lines: list[str] = []

            root = Path(repository.local_path)
            for file_path in iter_text_files(root):
                text = safe_read_text(file_path, self.settings.max_file_size_bytes)
                if not text:
                    continue
                parsed = self.parser.parse(file_path, text)
                changed, file_record = await self._upsert_file(repository.id, file_path, parsed, text)
                if changed:
                    await self._upsert_chunks(repository.id, file_record, text, parsed)
                file_counter += 1
                function_counter += len(parsed.functions)
                class_counter += len(parsed.classes)
                route_counter += len(parsed.routes)
                language_counter[parsed.language] += 1
                framework_hints.update(self._detect_framework_hints(file_path, text))
                collected_summary_lines.append(f"{parsed.path}: {self._build_file_summary(parsed)}")

            repository.scan_status = "scanned"
            repository.summary = self._build_project_summary(repository.full_name, collected_summary_lines)
            repository.language_summary = dict(language_counter)
            repository.framework_summary = dict(framework_hints)
            await self.session.commit()

            scan_run.status = "completed"
            scan_run.file_count = file_counter
            scan_run.function_count = function_counter
            scan_run.class_count = class_counter
            scan_run.route_count = route_counter
            await self.session.commit()
            await self.session.refresh(scan_run)
            return scan_run
        except Exception as exc:
            scan_run.status = "failed"
            scan_run.error_message = str(exc)
            repository.scan_status = "failed"
            await self.session.commit()
            raise

    async def _upsert_file(self, repository_id: str, file_path: Path, parsed: ParsedFile, text: str) -> tuple[bool, FileRecord]:
        content_hash = hash_content(text)
        result = await self.session.execute(
            select(FileRecord).where(FileRecord.repository_id == repository_id, FileRecord.path == str(file_path))
        )
        file_record = result.scalar_one_or_none()
        summary = self._build_file_summary(parsed)
        if file_record:
            if file_record.content_hash == content_hash:
                return False, file_record
            file_record.language = parsed.language
            file_record.content_hash = content_hash
            file_record.summary = summary
            file_record.symbols_json = {"functions": parsed.functions, "classes": parsed.classes, "imports": parsed.imports, "routes": parsed.routes, "symbols": parsed.symbols}
            await self.session.commit()
            await self.session.refresh(file_record)
            return True, file_record

        file_record = FileRecord(
            repository_id=repository_id,
            path=str(file_path),
            language=parsed.language,
            content_hash=content_hash,
            summary=summary,
            symbols_json={"functions": parsed.functions, "classes": parsed.classes, "imports": parsed.imports, "routes": parsed.routes, "symbols": parsed.symbols},
        )
        self.session.add(file_record)
        await self.session.commit()
        await self.session.refresh(file_record)
        return True, file_record

    async def _upsert_chunks(self, repository_id: str, file_record: FileRecord, text: str, parsed: ParsedFile) -> None:
        chunk_metas = await self.chunker.chunk_file(self.session, repository_id, Path(file_record.path), text, reindex=True)
        if not chunk_metas:
            return
        chunk_ids = [cm["id"] for cm in chunk_metas]
        result = await self.session.execute(
            select(ChunkRecord).where(ChunkRecord.id.in_(chunk_ids)).order_by(ChunkRecord.chunk_index)
        )
        chunk_records = list(result.scalars().all())
        contents = [cr.content for cr in chunk_records]
        embeddings = await self.ollama.embed_texts(contents)
        chroma_ids = []
        chroma_docs = []
        chroma_embs = []
        chroma_metas = []
        for idx, cr in enumerate(chunk_records):
            meta = dict(cr.metadata_json or {})
            meta.update({"repository_id": repository_id, "file_id": file_record.id, "path": file_record.path, "chunk_index": cr.chunk_index})
            chroma_ids.append(cr.id)
            chroma_docs.append(cr.content)
            chroma_embs.append(embeddings[idx])
            chroma_metas.append(meta)
            cr.embedding_id = cr.id
        self.chroma.upsert_chunks(ids=chroma_ids, documents=chroma_docs, embeddings=chroma_embs, metadatas=chroma_metas)
        await self.session.commit()

    @staticmethod
    def _build_file_summary(parsed: ParsedFile) -> str:
        parts = []
        if parsed.functions:
            parts.append(f"functions={len(parsed.functions)}")
        if parsed.classes:
            parts.append(f"classes={len(parsed.classes)}")
        if parsed.imports:
            parts.append(f"imports={len(parsed.imports)}")
        if parsed.routes:
            parts.append(f"routes={len(parsed.routes)}")
        return ", ".join(parts) if parts else "no major symbols detected"

    @staticmethod
    def _build_project_summary(repository_name: str, file_summaries: list[str]) -> str:
        header = f"Repository {repository_name} was scanned locally."
        if not file_summaries:
            return f"{header} No indexed files were found."
        preview = "\n".join(file_summaries[:25])
        return f"{header}\n\nKey files:\n{preview}"

    @staticmethod
    def _detect_framework_hints(file_path: Path, text: str) -> list[str]:
        name = file_path.name.lower()
        content = text.lower()
        hints: list[str] = []
        if name in {"next.config.js", "next.config.mjs", "next.config.ts"} or "next" in content:
            hints.append("nextjs")
        if name in {"tailwind.config.js", "tailwind.config.ts"} or "tailwindcss" in content:
            hints.append("tailwindcss")
        if "fastapi" in content:
            hints.append("fastapi")
        if "celery" in content:
            hints.append("celery")
        if "chromadb" in content or "chromadb" in name:
            hints.append("chromadb")
        if "ollama" in content:
            hints.append("ollama")
        return hints
