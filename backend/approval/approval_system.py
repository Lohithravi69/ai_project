from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import ApprovalRequestRecord, ExecutionPlanRecord
from backend.models.schemas import ApprovalAction, ApprovalRequestRead


class ApprovalSystem:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_approval_request(
        self,
        plan_id: str,
        diff_preview: str = "",
        explanation: str = "",
        execution_id: str | None = None,
    ) -> ApprovalRequestRead:
        record = ApprovalRequestRecord(
            plan_id=plan_id,
            diff_preview=diff_preview,
            explanation=explanation,
            status="pending",
            execution_id=execution_id,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return self._record_to_read(record)

    async def get_approval_request(self, approval_id: str) -> ApprovalRequestRead | None:
        record = await self.session.get(ApprovalRequestRecord, approval_id)
        if not record:
            return None
        return self._record_to_read(record)

    async def list_approval_requests(
        self, plan_id: str | None = None, status: str | None = None, limit: int = 50
    ) -> list[ApprovalRequestRead]:
        from sqlalchemy import select

        query = select(ApprovalRequestRecord).order_by(ApprovalRequestRecord.created_at.desc())
        if plan_id:
            query = query.where(ApprovalRequestRecord.plan_id == plan_id)
        if status:
            query = query.where(ApprovalRequestRecord.status == status)
        result = await self.session.execute(query.limit(limit))
        return [self._record_to_read(r) for r in result.scalars().all()]

    async def approve(self, approval_id: str, action: ApprovalAction) -> ApprovalRequestRead:
        record = await self.session.get(ApprovalRequestRecord, approval_id)
        if not record:
            raise ValueError(f"Approval request not found: {approval_id}")
        if record.status != "pending":
            raise ValueError(f"Approval request is already {record.status}")

        record.status = "approved" if action.approved else "rejected"
        record.reviewer = action.reviewer or ""
        record.reviewed_at = datetime.now(timezone.utc)
        if not action.approved:
            record.rejection_reason = action.rejection_reason or ""

        plan_record = await self.session.get(ExecutionPlanRecord, record.plan_id)
        if plan_record:
            plan_record.approval_status = record.status

        await self.session.commit()
        await self.session.refresh(record)
        return self._record_to_read(record)

    async def reject(self, approval_id: str, reason: str = "", reviewer: str = "") -> ApprovalRequestRead:
        return await self.approve(approval_id, ApprovalAction(approved=False, rejection_reason=reason, reviewer=reviewer))

    def _record_to_read(self, record: ApprovalRequestRecord) -> ApprovalRequestRead:
        return ApprovalRequestRead(
            id=record.id,
            plan_id=record.plan_id,
            diff_preview=record.diff_preview,
            explanation=record.explanation,
            status=record.status,
            reviewer=record.reviewer,
            reviewed_at=record.reviewed_at,
            rejection_reason=record.rejection_reason,
            created_at=record.created_at,
            execution_id=record.execution_id,
        )
