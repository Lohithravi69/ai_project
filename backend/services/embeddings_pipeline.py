from __future__ import annotations

from typing import Any, List
from math import ceil

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.embeddings.ollama_client import OllamaClient
from backend.embeddings.chroma_service import ChromaService
from backend.database.models import ChunkRecord


class EmbeddingsPipeline:
    """Batch embed chunks using Ollama and upsert into ChromaDB and Postgres metadata."""

    def __init__(self, ollama: OllamaClient, chroma: ChromaService, batch_size: int = 16) -> None:
        self.ollama = ollama
        self.chroma = chroma
        self.batch_size = batch_size
        self.settings = get_settings()

    async def process_pending_chunks(self, session: AsyncSession, repository_id: str, limit: int = 1000) -> int:
        """Find chunks without embeddings and process them in batches. Returns number processed."""

        stmt = select(ChunkRecord).where(ChunkRecord.repository_id == repository_id, ChunkRecord.embedding_id == "").limit(limit)
        result = await session.execute(stmt)
        rows = result.scalars().all()
        if not rows:
            return 0

        total = len(rows)
        batches = ceil(total / self.batch_size)
        processed = 0

        for b in range(batches):
            batch_items = rows[b * self.batch_size : (b + 1) * self.batch_size]
            texts = [item.content for item in batch_items]
            try:
                embeddings = await self.ollama.embed_texts(texts)
            except Exception as exc:  # pragma: no cover - runtime external call
                raise

            ids = [item.id for item in batch_items]
            metadatas = []
            for item in batch_items:
                meta = dict(item.metadata_json or {})
                meta.update({"repository_id": item.repository_id, "file_id": item.file_id, "chunk_index": item.chunk_index})
                metadatas.append(meta)

            # upsert into Chroma
            self.chroma.upsert_chunks(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)

            # update chunk.embedding_id and embeddings_meta table
            for item, emb in zip(batch_items, embeddings):
                # set embedding_id to the chunk id for traceability
                await session.execute(
                    update(ChunkRecord).where(ChunkRecord.id == item.id).values(embedding_id=item.id)
                )
                # insert into embeddings_meta
                await session.execute(
                    """
                    INSERT INTO embeddings_meta (embedding_id, chunk_id, chroma_id, model_name, dimension, vector, created_at)
                    VALUES (:embedding_id, :chunk_id, :chroma_id, :model_name, :dimension, :vector, NOW())
                    ON CONFLICT (embedding_id) DO UPDATE SET chroma_id = EXCLUDED.chroma_id, model_name = EXCLUDED.model_name, dimension = EXCLUDED.dimension, vector = EXCLUDED.vector
                    """,
                    {
                        "embedding_id": item.id,
                        "chunk_id": item.id,
                        "chroma_id": item.id,
                        "model_name": self.settings.ollama_embed_model,
                        "dimension": len(emb),
                        "vector": emb,
                    },
                )

            await session.commit()
            processed += len(batch_items)

        return processed
