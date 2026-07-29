from __future__ import annotations

import asyncio

from celery import Celery

from backend.config import get_settings
from backend.database.session import async_session_maker
from backend.database.models import RepositoryRecord
from backend.services.repository_sync_service import RepositorySyncService
from sqlalchemy import select

settings = get_settings()

celery_app = Celery("ai_dev_os", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    beat_schedule={
        "sync-all-repositories-every-5-minutes": {
            "task": "sync_all_repositories",
            "schedule": 300.0,
        }
    },
)


@celery_app.task(name="scan_repository")
def scan_repository_task(repository_id: str) -> str:
    """Incrementally sync and index a repository in the background."""

    async def _run() -> None:
        async with async_session_maker() as session:
            service = RepositorySyncService(session)
            await service.sync_repository(repository_id)

    asyncio.run(_run())
    return repository_id


@celery_app.task(name="sync_all_repositories")
def sync_all_repositories_task() -> int:
    async def _run() -> int:
        async with async_session_maker() as session:
            result = await session.execute(select(RepositoryRecord.id).where(RepositoryRecord.is_active.is_(True)))
            repository_ids = [row[0] for row in result.all()]
            service = RepositorySyncService(session)
            processed = 0
            for repository_id in repository_ids:
                try:
                    await service.sync_repository(repository_id)
                    processed += 1
                except Exception:
                    continue
            return processed

    return asyncio.run(_run())

