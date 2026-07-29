from __future__ import annotations

import time
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from backend.embeddings.ollama_client import OllamaClient
from backend.services.observability_service import ObservabilityService
from backend.services.retriever import Retriever
from backend.services.memory_service import MemoryService


class RagOrchestrator:
    """Retrieve relevant context, construct prompt, and call Ollama chat model."""

    def __init__(self, ollama: OllamaClient, retriever: Retriever, memory: MemoryService):
        self.ollama = ollama
        self.retriever = retriever
        self.memory = memory
        self.observability = ObservabilityService()

    async def answer(
        self,
        query: str,
        session_id: str | None = None,
        repository_id: str | None = None,
        top_k: int = 8,
        db_session: AsyncSession | None = None,
    ) -> Dict[str, Any]:
        # Step 1: retrieve contexts
        started_at = time.monotonic()
        contexts = await self.retriever.retrieve(query, repository_id=repository_id, top_k=top_k)

        # Step 2: fetch short-term memory
        stm = []
        if session_id:
            stm = await self.memory.retrieve_short_term(session_id=session_id, k=5)

        # Step 3: build prompt
        system_prompt = (
            "You are an AI assistant specialized in explaining codebases. Use the provided contexts and memories only. "
            "Cite sources by file path and chunk id where possible."
        )

        context_texts = []
        sources = []
        for c in contexts:
            content = c.get("content")
            meta = c.get("metadata") or {}
            source = meta.get("file_path") or meta.get("repository_id") or c.get("id")
            context_texts.append(f"SOURCE: {source}\n{content}")
            sources.append({"id": c.get("id"), "score": c.get("score"), "metadata": meta})

        memory_text = "\n".join([m.get("content") for m in stm]) if stm else ""

        user_message = """
        Query:
        {query}

        Contexts:
        {contexts}

        Short-term memory:
        {memory}

        Provide a concise, precise answer. Include references to context sources.
        """.format(query=query, contexts="\n---\n".join(context_texts[:8]), memory=memory_text)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        answer = await self.ollama.chat(messages)
        latency_ms = int((time.monotonic() - started_at) * 1000)
        prompt_tokens = max(1, len(user_message) // 4)
        completion_tokens = max(1, len(answer) // 4)
        debug = {
            "retrieved_chunks": [
                {
                    "id": c.get("id"),
                    "score": c.get("score"),
                    "metadata": c.get("metadata") or {},
                    "content": c.get("content"),
                }
                for c in contexts
            ],
            "prompt_context": user_message,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "context_size": len(user_message),
            "retrieved_chunk_count": len(contexts),
            "response_time_ms": latency_ms,
            "estimated_local_model_memory_mb": 2048,
        }

        if db_session is not None:
            try:
                await self.observability.log_retrieval(
                    db_session,
                    repository_id,
                    query,
                    query_meta={
                        "session_id": session_id,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "context_size": len(user_message),
                        "prompt_context": user_message,
                    },
                    results=sources,
                    top_k=top_k,
                    latency_ms=latency_ms,
                )
            except Exception:
                pass

        return {"answer": answer, "sources": sources, "debug": debug}
