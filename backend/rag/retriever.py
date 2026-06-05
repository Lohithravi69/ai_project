from __future__ import annotations

from backend.embeddings.chroma_service import ChromaService
from backend.embeddings.ollama_client import OllamaClient


class Retriever:
    """Semantic retrieval over repository chunks."""

    def __init__(self, ollama_client: OllamaClient, chroma_service: ChromaService) -> None:
        self.ollama_client = ollama_client
        self.chroma_service = chroma_service

    async def retrieve(self, repository_id: str, query: str, top_k: int = 5) -> list[dict[str, object]]:
        query_embedding = await self.ollama_client.embed_text(query)
        return self.chroma_service.search(query_embedding=query_embedding, repository_id=repository_id, top_k=top_k)
