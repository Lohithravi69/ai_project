from __future__ import annotations

from typing import Any

import httpx


class OllamaClient:
    """Talk to the local Ollama server for chat and embedding requests."""

    def __init__(self, base_url: str, chat_model: str, embed_model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embed_model = embed_model

    async def embed_text(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.embed_model, "prompt": text},
            )
            response.raise_for_status()
            payload = response.json()
            return payload["embedding"]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            embeddings.append(await self.embed_text(text))
        return embeddings

    async def chat(self, messages: list[dict[str, Any]]) -> str:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={"model": self.chat_model, "messages": messages, "stream": False},
            )
            response.raise_for_status()
            payload = response.json()
            return payload["message"]["content"]
