from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.embeddings.chroma_service import ChromaService
from backend.embeddings.ollama_client import OllamaClient


class MemoryService:
    """Two-tier memory service:

    - Short-term: Redis lists per session (fast, TTL)
    - Long-term: Chroma-backed embeddings with Postgres audit
    """

    def __init__(self, settings: Optional[object] = None) -> None:
        self.settings = settings or get_settings()
        self.redis = aioredis.from_url(self.settings.redis_url, decode_responses=True)
        self.chroma = ChromaService(self.settings.chroma_persist_directory)
        self.ollama = OllamaClient(self.settings.ollama_base_url, self.settings.ollama_chat_model, self.settings.ollama_embed_model)
        self.short_term_ttl = int(getattr(self.settings, "short_term_memory_ttl_seconds", 60 * 60 * 24))

    async def store_short_term(self, session_id: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        item = {"id": str(uuid4()), "content": content, "metadata": metadata or {}, "ts": datetime.utcnow().isoformat()}
        key = f"memory:short:{session_id}"
        await self.redis.rpush(key, json.dumps(item))
        await self.redis.expire(key, self.short_term_ttl)
        # audit in DB
        await self._insert_conversation_memory_row(session=None, session_id=session_id, memory_type="short_term", title=None, content=content, metadata=item["metadata"], embedding_ref=None)
        return item["id"]

    async def retrieve_short_term(self, session_id: str, k: int = 10) -> List[Dict[str, Any]]:
        key = f"memory:short:{session_id}"
        length = await self.redis.llen(key)
        if length == 0:
            return []
        start = max(0, length - k)
        items = await self.redis.lrange(key, start, length - 1)
        return [json.loads(i) for i in items]

    async def store_long_term(self, db_session: AsyncSession, session_id: Optional[str], title: str, content: str, metadata: Optional[Dict[str, Any]] = None, repository_id: Optional[str] = None) -> str:
        """Embed content, upsert into Chroma, and persist metadata in Postgres conversation_memory and embeddings_meta."""
        emb = await self.ollama.embed_text(content)
        emb_id = str(uuid4())
        chroma_id = emb_id
        # upsert to chroma
        docs = [content]
        embs = [emb]
        metadatas = [{"session_id": session_id, "title": title, "repository_id": repository_id, **(metadata or {})}]
        self.chroma.upsert_chunks(ids=[emb_id], documents=docs, embeddings=embs, metadatas=metadatas)

        # insert conversation_memory and embeddings_meta
        await db_session.execute(
            text(
                """
                INSERT INTO conversation_memory (memory_id, session_id, memory_type, title, content, metadata_json, embedding_ref, created_at, last_accessed_at)
                VALUES (:memory_id, :session_id, :memory_type, :title, :content, :metadata_json, :embedding_ref, NOW(), NOW())
                """
            ),
            {
                "memory_id": emb_id,
                "session_id": session_id,
                "memory_type": "long_term",
                "title": title,
                "content": content,
                "metadata_json": json.dumps(metadata or {}),
                "embedding_ref": emb_id,
            },
        )

        await db_session.execute(
            text(
                """
                INSERT INTO embeddings_meta (embedding_id, chunk_id, chroma_id, model_name, dimension, vector, created_at)
                VALUES (:embedding_id, :chunk_id, :chroma_id, :model_name, :dimension, :vector, NOW())
                ON CONFLICT (embedding_id) DO UPDATE SET chroma_id = EXCLUDED.chroma_id, model_name = EXCLUDED.model_name, dimension = EXCLUDED.dimension, vector = EXCLUDED.vector
                """
            ),
            {
                "embedding_id": emb_id,
                "chunk_id": emb_id,
                "chroma_id": chroma_id,
                "model_name": self.settings.ollama_embed_model,
                "dimension": len(emb),
                "vector": json.dumps(emb),
            },
        )

        await db_session.commit()
        return emb_id

    async def search_long_term(self, query: str, repository_id: Optional[str] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        emb = await self.ollama.embed_text(query)
        return self.chroma.search(query_embedding=emb, repository_id=repository_id or "", top_k=top_k)

    async def _insert_conversation_memory_row(self, session: Optional[AsyncSession], session_id: Optional[str], memory_type: str, title: Optional[str], content: str, metadata: Dict[str, Any], embedding_ref: Optional[str]):
        # If a DB session is provided, use it. Otherwise, attempt to create a short-lived connection is not available here.
        if session is None:
            return
        await session.execute(
            text(
                """
                INSERT INTO conversation_memory (memory_id, session_id, memory_type, title, content, metadata_json, embedding_ref, created_at, last_accessed_at)
                VALUES (:memory_id, :session_id, :memory_type, :title, :content, :metadata_json, :embedding_ref, NOW(), NOW())
                """
            ),
            {
                "memory_id": str(uuid4()),
                "session_id": session_id,
                "memory_type": memory_type,
                "title": title,
                "content": content,
                "metadata_json": json.dumps(metadata or {}),
                "embedding_ref": embedding_ref,
            },
        )

    async def consolidate_long_term(self, db_session: AsyncSession) -> int:
        """Simple consolidation: merge exact-duplicate long-term memories by content.

        Returns number of merged entries.
        """
        # find duplicates by exact content match
        res = await db_session.execute(text("SELECT content, array_agg(memory_id) as ids, COUNT(*) as cnt FROM conversation_memory WHERE memory_type='long_term' GROUP BY content HAVING COUNT(*) > 1"))
        rows = res.fetchall()
        merged = 0
        for row in rows:
            ids = row[1]
            keep = ids[0]
            remove = ids[1:]
            if not remove:
                continue
            # delete duplicates and keep one
            await db_session.execute(text("DELETE FROM conversation_memory WHERE memory_id = ANY(:remove_ids)"), {"remove_ids": remove})
            merged += len(remove)

        await db_session.commit()
        return merged
