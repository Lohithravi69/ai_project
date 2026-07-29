from __future__ import annotations

import asyncio
from typing import Any

import httpx


class OllamaClient:
    """Talk to the local Ollama server for chat and embedding requests."""

    def __init__(self, base_url: str, chat_model: str, embed_model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embed_model = embed_model

    async def _request_json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        delay = 1.0
        last_error: Exception | None = None
        for _attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=180.0) as client:
                    response = await client.request(method, f"{self.base_url}{path}", json=payload)
                    response.raise_for_status()
                    return response.json()
            except Exception as exc:  # pragma: no cover - defensive
                last_error = exc
                await asyncio.sleep(delay)
                delay *= 2
        if last_error:
            raise last_error
        raise RuntimeError("Ollama request failed")

    async def is_available(self) -> bool:
        try:
            await self._request_json("GET", "/api/tags")
            return True
        except Exception:
            return False

    async def ensure_models(self) -> None:
        try:
            payload = await self._request_json("GET", "/api/tags")
            existing = {model.get("name", "") for model in payload.get("models", [])}
            for model_name in [self.chat_model, self.embed_model]:
                if model_name in existing:
                    continue
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream("POST", f"{self.base_url}/api/pull", json={"name": model_name}) as response:
                        response.raise_for_status()
                        await response.aread()
        except Exception:
            return

    async def embed_text(self, text: str) -> list[float]:
        payload = await self._request_json("POST", "/api/embeddings", {"model": self.embed_model, "prompt": text})
        return payload["embedding"]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        tasks = [self.embed_text(text) for text in texts]
        return list(await asyncio.gather(*tasks))

    async def chat(self, messages: list[dict[str, Any]]) -> str:
        payload = await self._request_json("POST", "/api/chat", {"model": self.chat_model, "messages": messages, "stream": False})
        return payload["message"]["content"]
