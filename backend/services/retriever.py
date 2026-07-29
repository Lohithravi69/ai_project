from __future__ import annotations

import re
from typing import Any, List, Dict

from backend.embeddings.chroma_service import ChromaService
from backend.embeddings.ollama_client import OllamaClient
from backend.services.memory_service import MemoryService


CHUNK_TYPE_BOOST = {
    "function": 1.25,
    "class": 1.20,
    "route": 1.15,
    "api": 1.10,
    "config": 0.90,
    "dependency": 0.85,
    "other": 1.0,
}


class Retriever:
    """Combine long-term Chroma search with short-term Redis memory and rerank results."""

    def __init__(self, chroma: ChromaService, ollama: OllamaClient, memory: MemoryService):
        self.chroma = chroma
        self.ollama = ollama
        self.memory = memory

    async def retrieve(self, query: str, repository_id: str | None = None, top_k: int = 8, chunk_type: str | None = None) -> List[Dict[str, Any]]:
        query_emb = await self.ollama.embed_text(query)

        chroma_hits = self.chroma.search(query_embedding=query_emb, repository_id=repository_id or "", top_k=top_k * 2, chunk_type=chunk_type)

        short_term = await self.memory.retrieve_short_term(session_id=repository_id or "", k=5) if repository_id else []

        short_hits = []
        for item in short_term:
            short_hits.append({"id": item.get("id"), "content": item.get("content"), "metadata": item.get("metadata", {}), "score": 1.0})

        all_hits = short_hits + chroma_hits
        reranked = self._rerank(query, all_hits)
        seen = set()
        merged: List[Dict[str, Any]] = []
        for hit in reranked:
            hid = hit.get("id") or hit.get("content")[:64]
            if hid in seen:
                continue
            seen.add(hid)
            merged.append(hit)
            if len(merged) >= top_k:
                break
        return merged

    @staticmethod
    def _rerank(query: str, hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        query_tokens = set(re.findall(r"\w+", query.lower()))

        for hit in hits:
            score = hit.get("score", 0.0)
            metadata = hit.get("metadata") or {}
            chunk_type = metadata.get("chunk_type") or "other"
            content = hit.get("content") or ""

            boost = CHUNK_TYPE_BOOST.get(chunk_type, 1.0)
            content_tokens = set(re.findall(r"\w+", content.lower()))
            overlap = len(query_tokens & content_tokens)
            keyword_boost = 1.0 + (overlap / max(len(query_tokens), 1)) * 0.3
            hit["score"] = round(score * boost * keyword_boost, 6)

        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits
