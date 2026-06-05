from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.orchestrator import AgentOrchestrator
from backend.database.models import ChatMessage, ChatSession, RepositoryRecord
from backend.embeddings.chroma_service import ChromaService
from backend.embeddings.ollama_client import OllamaClient
from backend.rag.retriever import Retriever


class ChatService:
    """Context-aware repository assistant using RAG over local project chunks."""

    def __init__(self, session: AsyncSession, ollama: OllamaClient, chroma: ChromaService) -> None:
        self.session = session
        self.ollama = ollama
        self.retriever = Retriever(ollama, chroma)

    async def answer(self, repository_id: str, question: str, session_id: str | None = None) -> tuple[str, str, list[dict[str, object]]]:
        repository = await self.session.get(RepositoryRecord, repository_id)
        if not repository:
            raise ValueError("Repository not found")

        chat_session = await self._get_or_create_session(repository_id, session_id)
        sources = await self.retriever.retrieve(repository_id=repository_id, query=question, top_k=5)
        system_prompt = AgentOrchestrator.build_system_prompt(repository.full_name, sources)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]
        answer = await self.ollama.chat(messages)
        self.session.add(ChatMessage(session_id=chat_session.id, role="user", content=question))
        self.session.add(ChatMessage(session_id=chat_session.id, role="assistant", content=answer))
        await self.session.commit()
        return answer, chat_session.id, sources

    async def _get_or_create_session(self, repository_id: str, session_id: str | None) -> ChatSession:
        if session_id:
            existing = await self.session.get(ChatSession, session_id)
            if existing:
                return existing
        chat_session = ChatSession(repository_id=repository_id)
        self.session.add(chat_session)
        await self.session.commit()
        await self.session.refresh(chat_session)
        return chat_session
