from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.router import _ollama_client
from backend.database.session import get_session
from backend.embeddings.chroma_service import ChromaService
from backend.services.memory_service import MemoryService
from backend.services.retriever import Retriever


router = APIRouter(prefix="/api/v2")


class SearchRequest(BaseModel):
    query: str
    repository_id: str | None = None
    top_k: int = 8


class SearchResult(BaseModel):
    id: str
    content: str
    metadata: dict
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]


@router.post("/search/semantic", response_model=SearchResponse)
async def semantic_search(payload: SearchRequest, session: AsyncSession = Depends(get_session)):
    ollama = _ollama_client()
    chroma = ChromaService("./vector_store/chroma")
    memory = MemoryService()
    retriever = Retriever(chroma, ollama, memory)

    try:
        results = await retriever.retrieve(payload.query, repository_id=payload.repository_id, top_k=payload.top_k)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SearchResponse(results=[SearchResult(**r) for r in results])
