from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.scanner_service import ScannerService


class ScanWorkflow:
    """Orchestrate repository scanning as a reusable workflow."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.scanner = ScannerService(session)

    async def run(self, repository_id: str):
        return await self.scanner.scan_repository(repository_id)
