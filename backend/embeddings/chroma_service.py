from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings


class ChromaService:
    """Persist repository chunks for semantic retrieval."""

    def __init__(self, persist_directory: str) -> None:
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(name="repository_chunks")

    def upsert_chunks(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        self._collection.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)

    def search(self, query_embedding: list[float], repository_id: str, top_k: int = 5, chunk_type: str | None = None) -> list[dict[str, Any]]:
        where_filter: dict[str, Any] = {"repository_id": repository_id}
        if chunk_type:
            where_filter["chunk_type"] = chunk_type
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        hits: list[dict[str, Any]] = []
        for index, document in enumerate(documents):
            hits.append(
                {
                    "id": result.get("ids", [[]])[0][index],
                    "content": document,
                    "metadata": metadatas[index] if index < len(metadatas) else {},
                    "score": 1.0 - float(distances[index]) if index < len(distances) else 0.0,
                }
            )
        return hits

    def delete_chunks(self, ids: list[str]) -> None:
        if not ids:
            return
        self._collection.delete(ids=ids)
