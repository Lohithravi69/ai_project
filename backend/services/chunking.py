from __future__ import annotations

from pathlib import Path
from typing import Any, List
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import ChunkRecord, FileRecord, RepositoryRecord
from backend.parsers.tree_sitter_parser import TreeSitterParser
from backend.utils.files import hash_content, chunk_text, detect_language


class AdvancedChunker:
    """Create semantic chunks for files using Tree-sitter when available.

    Produces chunk types: function, class, route, api, config, dependency, other
    """

    def __init__(self) -> None:
        self._parser = TreeSitterParser()

    async def chunk_file(
        self, session: AsyncSession, repository_id: str, file_path: Path | str, content: str, reindex: bool = False
    ) -> List[dict[str, Any]]:
        """Chunk a single file and persist chunks to the DB. Returns created chunk metadata list."""

        if isinstance(file_path, str):
            file_path = Path(file_path)

        repo = await session.scalar(select(RepositoryRecord).where(RepositoryRecord.id == repository_id))
        if not repo:
            raise RuntimeError(f"Repository {repository_id} not found")

        file_path_str = str(file_path)
        file_hash = hash_content(content)

        existing_file = await session.scalar(
            select(FileRecord).where(FileRecord.repository_id == repository_id, FileRecord.path == file_path_str)
        )

        if existing_file and existing_file.content_hash == file_hash and not reindex:
            return []

        if existing_file:
            await session.execute(delete(ChunkRecord).where(ChunkRecord.file_id == existing_file.id))
            existing_file.content_hash = file_hash
            existing_file.summary = ""
            existing_file.symbols_json = {}
            file_id = existing_file.id
        else:
            file_id = str(uuid4())
            new_file = FileRecord(
                id=file_id,
                repository_id=repository_id,
                path=file_path_str,
                language=detect_language(file_path),
                content_hash=file_hash,
                summary="",
                symbols_json={},
            )
            session.add(new_file)

        parsed = self._parser.parse(file_path, content)

        chunks: List[dict[str, Any]] = []
        index = 0

        # function chunks
        for fname in parsed.functions:
            snippet = self._extract_snippet_for_symbol(content, fname, parsed.language)
            meta = {
                "chunk_type": "function",
                "function_name": fname,
                "class_name": None,
                "language": parsed.language,
                "dependencies": parsed.imports,
            }
            chunk = ChunkRecord(
                id=str(uuid4()),
                file_id=file_id,
                repository_id=repository_id,
                chunk_index=index,
                content=snippet,
                embedding_id="",
                metadata_json=meta,
            )
            session.add(chunk)
            chunks.append({"id": chunk.id, "type": "function", "index": index})
            index += 1

        # class chunks
        for cname in parsed.classes:
            snippet = self._extract_snippet_for_symbol(content, cname, parsed.language, kind="class")
            meta = {
                "chunk_type": "class",
                "function_name": None,
                "class_name": cname,
                "language": parsed.language,
                "dependencies": parsed.imports,
            }
            chunk = ChunkRecord(
                id=str(uuid4()),
                file_id=file_id,
                repository_id=repository_id,
                chunk_index=index,
                content=snippet,
                embedding_id="",
                metadata_json=meta,
            )
            session.add(chunk)
            chunks.append({"id": chunk.id, "type": "class", "index": index})
            index += 1

        # route chunks
        for route in parsed.routes:
            # include surrounding code for the route occurrence
            snippet = self._extract_snippet_for_route(content, route)
            meta = {"chunk_type": "route", "route": route, "language": parsed.language, "dependencies": parsed.imports}
            chunk = ChunkRecord(
                id=str(uuid4()),
                file_id=file_id,
                repository_id=repository_id,
                chunk_index=index,
                content=snippet,
                embedding_id="",
                metadata_json=meta,
            )
            session.add(chunk)
            chunks.append({"id": chunk.id, "type": "route", "index": index})
            index += 1

        # configuration / dependency files (single chunk)
        if file_path.name in {"requirements.txt", "package.json", "pyproject.toml", "Pipfile", "Dockerfile"}:
            snippet = content
            meta = {"chunk_type": "dependency", "language": parsed.language, "dependencies": parsed.imports}
            chunk = ChunkRecord(
                id=str(uuid4()),
                file_id=file_id,
                repository_id=repository_id,
                chunk_index=index,
                content=snippet,
                embedding_id="",
                metadata_json=meta,
            )
            session.add(chunk)
            chunks.append({"id": chunk.id, "type": "dependency", "index": index})
            index += 1

        # fallback: if no chunks created, chunk the file by semantic lines
        if index == 0:
            parts = chunk_text(content, max_chars=4000)
            for part in parts:
                meta = {"chunk_type": "other", "language": parsed.language, "dependencies": parsed.imports}
                chunk = ChunkRecord(
                    id=str(uuid4()),
                    file_id=file_id,
                    repository_id=repository_id,
                    chunk_index=index,
                    content=part,
                    embedding_id="",
                    metadata_json=meta,
                )
                session.add(chunk)
                chunks.append({"id": chunk.id, "type": "other", "index": index})
                index += 1

        await session.flush()
        return chunks

    @staticmethod
    def _extract_snippet_for_symbol(content: str, symbol: str, language: str, kind: str = "function") -> str:
        # naive extraction: find symbol occurrence and take following block until next top-level symbol
        lines = content.splitlines()
        pattern = None
        if language == "python":
            if kind == "function":
                pattern = f"def {symbol}"
            else:
                pattern = f"class {symbol}"
        else:
            pattern = symbol

        start_idx = 0
        for i, line in enumerate(lines):
            if pattern in line:
                start_idx = i
                break

        # capture until next top-level def/class (simple heuristic) or max lines
        end_idx = min(len(lines), start_idx + 200)
        for j in range(start_idx + 1, min(len(lines), start_idx + 200)):
            if language == "python" and (lines[j].startswith("def ") or lines[j].startswith("class ")):
                end_idx = j
                break

        snippet = "\n".join(lines[start_idx:end_idx]).strip()
        if not snippet:
            # fallback to a short context window
            snippet = "\n".join(lines[max(0, start_idx - 5) : min(len(lines), start_idx + 20)])
        return snippet

    @staticmethod
    def _extract_snippet_for_route(content: str, route_signature: str) -> str:
        # return a 100-line window containing the route signature
        lines = content.splitlines()
        start_idx = 0
        for i, line in enumerate(lines):
            if route_signature in line or route_signature.split()[-1] in line:
                start_idx = i
                break
        return "\n".join(lines[max(0, start_idx - 10) : min(len(lines), start_idx + 90)])
