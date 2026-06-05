from __future__ import annotations

from typing import Any, Dict, List

from backend.embeddings.ollama_client import OllamaClient
from backend.services.retriever import Retriever
from backend.services.memory_service import MemoryService


class RagOrchestrator:
    """Retrieve relevant context, construct prompt, and call Ollama chat model."""

    def __init__(self, ollama: OllamaClient, retriever: Retriever, memory: MemoryService):
        self.ollama = ollama
        self.retriever = retriever
        self.memory = memory

    async def answer(self, query: str, session_id: str | None = None, repository_id: str | None = None, top_k: int = 8) -> Dict[str, Any]:
        # Step 1: retrieve contexts
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
        return {"answer": answer, "sources": sources}
