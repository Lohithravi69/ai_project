from __future__ import annotations

import asyncio

from celery import Celery

from backend.config import get_settings
from backend.database.session import async_session_maker
from backend.services.scanner_service import ScannerService

settings = get_settings()

celery_app = Celery("ai_dev_os", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
)


@celery_app.task(name="scan_repository")
def scan_repository_task(repository_id: str) -> str:
    """Celery task entrypoint used by Celery workers.

    Celery runs tasks in a separate (sync) process, while the scanner uses
    SQLAlchemy async sessions. We bridge the gap with `asyncio.run()`.
    """

    async def _run() -> None:
        async with async_session_maker() as session:
            scanner = ScannerService(session)
            await scanner.scan_repository(repository_id)

    asyncio.run(_run())
    return repository_id

