from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.router import _ollama_client
from backend.database.session import get_session
from backend.embeddings.chroma_service import ChromaService
from backend.services.memory_service import MemoryService
from backend.services.retriever import Retriever
from backend.services.rag_orchestrator import RagOrchestrator


router = APIRouter(prefix="/api/v2")


class RagRequest(BaseModel):
    session_id: str | None = None
    repository_id: str | None = None
    query: str
    top_k: int = 8


class RagResponse(BaseModel):
    answer: str
    sources: list


@router.post("/chat/rag", response_model=RagResponse)
async def chat_rag(payload: RagRequest, session: AsyncSession = Depends(get_session)):
    ollama = _ollama_client()
    chroma = ChromaService("./vector_store/chroma")
    memory = MemoryService()
    retriever = Retriever(chroma, ollama, memory)
    orchestrator = RagOrchestrator(ollama, retriever, memory)

    try:
        res = await orchestrator.answer(payload.query, session_id=payload.session_id, repository_id=payload.repository_id, top_k=payload.top_k)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RagResponse(answer=res["answer"], sources=res["sources"]) 
