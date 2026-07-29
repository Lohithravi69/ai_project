from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import ChatMessage, ChatSession, ChunkRecord, FileRecord, RepositoryRecord
from backend.database.session import get_session

router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/metrics")
async def metrics(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    repository_count = await session.scalar(select(func.count()).select_from(RepositoryRecord))
    file_count = await session.scalar(select(func.count()).select_from(FileRecord))
    chunk_count = await session.scalar(select(func.count()).select_from(ChunkRecord))
    session_count = await session.scalar(select(func.count()).select_from(ChatSession))
    message_count = await session.scalar(select(func.count()).select_from(ChatMessage))

    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repositories": int(repository_count or 0),
        "files": int(file_count or 0),
        "chunks": int(chunk_count or 0),
        "chat_sessions": int(session_count or 0),
        "chat_messages": int(message_count or 0),
    }
