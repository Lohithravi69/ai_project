from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import ExecutionPlanRecord
from backend.models.schemas import ExecutionPlanCreate, ExecutionPlanRead
from backend.tool_registry.registry import ToolRegistry


class ActionPlanner:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.registry = ToolRegistry()

    async def create_plan(self, request: ExecutionPlanCreate) -> ExecutionPlanRead:
        start = time.perf_counter()
        execution_id = request.execution_id or str(uuid4())

        text_blob = " ".join([request.objective, request.request_text, " ".join(request.affected_files)]).lower()
        modifying = any(kw in text_blob for kw in ["write", "edit", "update", "create", "delete", "remove", "refactor", "implement", "patch", "commit", "rollback", "move"])

        all_tools = self.registry.list_tool_names()
        required_tools = ["ReadFile", "SearchRepository", "ListFiles", "GitStatus"]
        if modifying:
            required_tools.extend(["GitDiff", "CreateBranch", "CheckoutBranch", "WriteFile", "CreateFile", "DeleteFile", "MoveFile", "FormatCode", "RunPyTest", "CommitChanges", "RollbackCommit"])
        else:
            required_tools.extend(["GitDiff", "QueryVectorStore", "QueryPostgres"])

        if "test" in text_blob and "RunPyTest" not in required_tools:
            required_tools.append("RunPyTest")
        if "shell" in text_blob and "RunShellRestricted" not in required_tools:
            required_tools.append("RunShellRestricted")
        if "format" in text_blob and "FormatCode" not in required_tools:
            required_tools.append("FormatCode")

        required_tools = [t for t in required_tools if t in all_tools]

        risk_keywords = ["delete", "rollback", "overwrite", "migrate", "destroy"]
        risk = "high" if any(kw in text_blob for kw in risk_keywords) and modifying else "medium" if modifying else "low"

        execution_order = [
            {"order": 1, "title": "Intent Analysis", "description": "Clarify objective and determine whether the request modifies files.", "tools": [], "dry_run": True},
            {"order": 2, "title": "Task Breakdown", "description": "Identify affected repositories and files.", "tools": ["ReadFile", "SearchRepository", "ListFiles"], "dry_run": True},
            {"order": 3, "title": "Tool Selection", "description": "Select the minimal tool set needed for the request.", "tools": required_tools, "dry_run": True},
            {"order": 4, "title": "Dry Run Preview", "description": "Preview the proposed change before execution.", "tools": [t for t in required_tools if t not in {"QueryVectorStore", "QueryPostgres"}], "dry_run": True},
            {"order": 5, "title": "Risk Assessment", "description": f"Estimated risk: {risk}.", "tools": [], "dry_run": True},
            {"order": 6, "title": "Approval", "description": "Modifying actions require explicit human approval.", "tools": ["RollbackCommit"], "dry_run": True},
        ]

        duration = self._estimate_duration(required_tools)
        rollback_strategy = "Capture a checkpoint, restore the saved git SHA and branch, then resync metadata, graph, and vector index."

        duration_ms = int((time.perf_counter() - start) * 1000)

        plan_id = str(uuid4())
        record = ExecutionPlanRecord(
            id=plan_id,
            objective=request.objective,
            reasoning=request.reasoning or request.request_text,
            repository_ids_json=request.repository_ids,
            affected_files_json=request.affected_files,
            required_tools_json=required_tools,
            execution_order_json=execution_order,
            risk_score=risk,
            estimated_duration_ms=duration,
            rollback_strategy=rollback_strategy,
            approval_required=modifying,
            approval_status="pending" if modifying else "approved",
            execution_id=execution_id,
            pipeline_stage="plan",
            metrics_json={"planning_time_ms": duration_ms},
            ai_reasoning_json=request.ai_reasoning.model_dump(),
            plan_json={
                "objective": request.objective,
                "request_text": request.request_text,
                "reasoning": request.reasoning or request.request_text,
                "repository_ids": request.repository_ids,
                "affected_files": request.affected_files,
                "required_tools": required_tools,
                "execution_order": execution_order,
                "risk_score": risk,
                "estimated_duration_ms": duration,
                "rollback_strategy": rollback_strategy,
                "approval_required": modifying,
                "ai_reasoning": request.ai_reasoning.model_dump(),
            },
        )
        self.session.add(record)
        await self.session.commit()

        from backend.models.schemas import AIReasoning, AgentTraceEntry

        return ExecutionPlanRead(
            id=plan_id,
            objective=request.objective,
            reasoning=request.reasoning or request.request_text,
            repository_ids=request.repository_ids,
            affected_files=request.affected_files,
            required_tools=required_tools,
            execution_order=execution_order,
            risk_score=risk,
            estimated_duration_ms=duration,
            rollback_strategy=rollback_strategy,
            approval_required=modifying,
            approval_status="pending" if modifying else "approved",
            plan=record.plan_json,
            ai_reasoning=AIReasoning(**request.ai_reasoning.model_dump()),
            agent_trace=[AgentTraceEntry(**t) for t in record.agent_trace_json or []],
            architecture=record.architecture_json or {},
            agent_status=record.agent_status or "pending",
            created_at=record.created_at,
            updated_at=record.updated_at,
            execution_id=execution_id,
        )

    async def get_plan(self, plan_id: str) -> ExecutionPlanRead | None:
        record = await self.session.get(ExecutionPlanRecord, plan_id)
        if not record:
            return None
        return self._record_to_read(record)

    async def list_plans(self, limit: int = 50) -> list[ExecutionPlanRead]:
        from sqlalchemy import select

        query = select(ExecutionPlanRecord).order_by(ExecutionPlanRecord.created_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return [self._record_to_read(r) for r in result.scalars().all()]

    def _record_to_read(self, record: ExecutionPlanRecord) -> ExecutionPlanRead:
        from backend.models.schemas import AIReasoning, AgentTraceEntry

        return ExecutionPlanRead(
            id=record.id,
            objective=record.objective,
            reasoning=record.reasoning,
            repository_ids=record.repository_ids_json,
            affected_files=record.affected_files_json,
            required_tools=record.required_tools_json,
            execution_order=record.execution_order_json,
            risk_score=record.risk_score,
            estimated_duration_ms=record.estimated_duration_ms,
            rollback_strategy=record.rollback_strategy,
            approval_required=record.approval_required,
            approval_status=record.approval_status,
            plan=record.plan_json,
            ai_reasoning=AIReasoning(**(record.ai_reasoning_json or {})),
            agent_trace=[AgentTraceEntry(**t) for t in record.agent_trace_json or []],
            architecture=record.architecture_json or {},
            agent_status=record.agent_status or "pending",
            created_at=record.created_at,
            updated_at=record.updated_at,
            execution_id=record.execution_id,
        )

    def _estimate_duration(self, tools: list[str]) -> int:
        estimates = {
            "ReadFile": 500, "WriteFile": 1000, "CreateFile": 500, "DeleteFile": 500, "MoveFile": 500,
            "SearchRepository": 2000, "ListFiles": 500, "GitStatus": 500, "GitDiff": 1000,
            "CreateBranch": 1000, "CheckoutBranch": 1000, "CommitChanges": 2000, "RollbackCommit": 5000,
            "RunPyTest": 60000, "RunPlaywright": 60000, "RunShellRestricted": 10000, "FormatCode": 5000,
            "QueryVectorStore": 2000, "QueryPostgres": 2000, "ReadLogs": 1000, "RestartContainer": 10000,
        }
        total = sum(estimates.get(t, 1000) for t in tools)
        return total
