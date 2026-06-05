from __future__ import annotations

from typing import Any, List, Dict

from backend.embeddings.chroma_service import ChromaService
from backend.embeddings.ollama_client import OllamaClient
from backend.services.memory_service import MemoryService


class Retriever:
    """Combine long-term Chroma search with short-term Redis memory and rerank results."""

    def __init__(self, chroma: ChromaService, ollama: OllamaClient, memory: MemoryService):
        self.chroma = chroma
        self.ollama = ollama
        self.memory = memory

    async def retrieve(self, query: str, repository_id: str | None = None, top_k: int = 8) -> List[Dict[str, Any]]:
        # embed query
        query_emb = await self.ollama.embed_text(query)

        # search chroma
        chroma_hits = self.chroma.search(query_embedding=query_emb, repository_id=repository_id or "", top_k=top_k)

        # fetch short-term memory
        short_term = await self.memory.retrieve_short_term(session_id=repository_id or "", k=5) if repository_id else []

        # convert short-term into result-like dicts
        short_hits = []
        for item in short_term:
            short_hits.append({"id": item.get("id"), "content": item.get("content"), "metadata": item.get("metadata", {}), "score": 1.0})

        # merge lists, deduplicate by id/content
        seen = set()
        merged: List[Dict[str, Any]] = []
        for hit in short_hits + chroma_hits:
            hid = hit.get("id") or hit.get("content")[:64]
            if hid in seen:
                continue
            seen.add(hid)
            merged.append(hit)
            if len(merged) >= top_k:
                break

        return merged
