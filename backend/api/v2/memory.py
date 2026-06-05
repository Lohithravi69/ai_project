from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.session import get_session


router = APIRouter(prefix="/api/v2")


class MemoryRequest(BaseModel):
    repository_id: str | None = None
    session_id: str | None = None
    limit: int = 100


class MemoryEntry(BaseModel):
    id: str
    session_id: str | None
    repository_id: str | None
    memory_type: str
    content: str
    embedding_id: str | None = None
    metadata_json: dict = {}
    created_at: str | None = None


class MemoryResponse(BaseModel):
    entries: List[MemoryEntry]
    total: int


@router.post("/memory/conversation", response_model=MemoryResponse)
async def get_conversation_memory(payload: MemoryRequest, session: AsyncSession = Depends(get_session)):
    """Fetch conversation memory (long-term) for a repository or session."""
    try:
        query = text(
            "SELECT id, session_id, repository_id, memory_type, content, embedding_id, metadata_json, created_at "
            "FROM conversation_memory "
            "WHERE (:repo_id IS NULL OR repository_id = :repo_id) "
            "  AND (:session_id IS NULL OR session_id = :session_id) "
            "ORDER BY created_at DESC LIMIT :lim"
        )
        result = await session.execute(
            query,
            {
                "repo_id": payload.repository_id,
                "session_id": payload.session_id,
                "lim": payload.limit,
            },
        )
        rows = result.mappings().all()
        entries = [
            MemoryEntry(
                id=row["id"],
                session_id=row["session_id"],
                repository_id=row["repository_id"],
                memory_type=row["memory_type"],
                content=row["content"],
                embedding_id=row["embedding_id"],
                metadata_json=row.get("metadata_json", {}),
                created_at=str(row.get("created_at")) if row.get("created_at") else None,
            )
            for row in rows
        ]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MemoryResponse(entries=entries, total=len(entries))
