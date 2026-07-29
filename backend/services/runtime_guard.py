from __future__ import annotations

from dataclasses import asdict, dataclass

import httpx
import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.config import Settings


@dataclass(slots=True)
class DependencyStatus:
    name: str
    status: str
    detail: str = ""


class RuntimeGuard:
    """Check and warm up runtime dependencies without changing the architecture."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def check_database(self, engine: AsyncEngine) -> DependencyStatus:
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return DependencyStatus("postgres", "ok")
        except Exception as exc:  # pragma: no cover - defensive
            return DependencyStatus("postgres", "degraded", str(exc))

    async def check_redis(self) -> DependencyStatus:
        client = redis.from_url(self.settings.redis_url)
        try:
            await client.ping()
            return DependencyStatus("redis", "ok")
        except Exception as exc:  # pragma: no cover - defensive
            return DependencyStatus("redis", "degraded", str(exc))
        finally:
            await client.aclose()

    async def check_ollama(self) -> DependencyStatus:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.settings.ollama_base_url.rstrip('/')}/api/tags")
                response.raise_for_status()
                payload = response.json()
                models = [model.get("name", "") for model in payload.get("models", [])]
            detail = ", ".join(sorted(m for m in models if m))[:512]
            return DependencyStatus("ollama", "ok", detail)
        except Exception as exc:  # pragma: no cover - defensive
            return DependencyStatus("ollama", "degraded", str(exc))

    async def check_chroma(self) -> DependencyStatus:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.settings.chroma_api_url.rstrip('/')}/api/v1/heartbeat")
                response.raise_for_status()
            return DependencyStatus("chroma", "ok")
        except Exception as exc:  # pragma: no cover - defensive
            return DependencyStatus("chroma", "degraded", str(exc))

    async def ensure_ollama_models(self, required_models: list[str]) -> list[DependencyStatus]:
        statuses: list[DependencyStatus] = []
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.settings.ollama_base_url.rstrip('/')}/api/tags")
                response.raise_for_status()
                payload = response.json()
                existing = {model.get("name", "") for model in payload.get("models", [])}

                for model_name in required_models:
                    if model_name in existing:
                        statuses.append(DependencyStatus(model_name, "ok", "already present"))
                        continue

                    async with client.stream(
                        "POST",
                        f"{self.settings.ollama_base_url.rstrip('/')}/api/pull",
                        json={"name": model_name},
                        timeout=None,
                    ) as pull_response:
                        pull_response.raise_for_status()
                        await pull_response.aread()
                    statuses.append(DependencyStatus(model_name, "ok", "downloaded"))
        except Exception as exc:  # pragma: no cover - defensive
            for model_name in required_models:
                statuses.append(DependencyStatus(model_name, "degraded", str(exc)))
        return statuses

    async def snapshot(self, engine: AsyncEngine) -> list[DependencyStatus]:
        return [
            await self.check_database(engine),
            await self.check_redis(),
            await self.check_ollama(),
            await self.check_chroma(),
        ]

    @staticmethod
    def as_dicts(statuses: list[DependencyStatus]) -> list[dict[str, str]]:
        return [asdict(status) for status in statuses]