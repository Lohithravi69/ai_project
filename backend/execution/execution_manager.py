from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import ExecutionPlanRecord, ToolExecutionRecord
from backend.execution.checkpoint_engine import CheckpointEngine
from backend.execution.diff_engine import DiffEngine
from backend.execution.metrics import MetricsCollector
from backend.execution.rollback_engine import RollbackEngine
from backend.execution.security import PermissionValidator
from backend.execution.validation_engine import ValidationEngine
from backend.execution.workspace import WorkspaceManager
from backend.models.schemas import ToolRunRequest, ToolRunResponse
from backend.tool_registry.registry import ToolRegistry


class ExecutionManager:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.registry = ToolRegistry()
        self.checkpoint_engine = CheckpointEngine(session)
        self.rollback_engine = RollbackEngine(session)
        self.workspace_manager = WorkspaceManager(session)
        self.diff_engine = DiffEngine()
        self.validation_engine = ValidationEngine()
        self.security = PermissionValidator()

    async def run_full_pipeline(self, request: ToolRunRequest) -> ToolRunResponse:
        metrics = MetricsCollector()
        execution_id = request.execution_id or str(uuid4())
        checkpoint_id: str | None = None
        requires_approval = False
        workspace_id = request.workspace_id
        is_modifying = False
        plan_record: ExecutionPlanRecord | None = None

        async def _set_pipeline_stage(stage: str) -> None:
            if plan_record:
                plan_record.pipeline_stage = stage
                await self.session.commit()

        try:
            spec = self.registry.get_spec(request.tool_name)
            is_modifying = spec.permission_level == "write"
        except ValueError:
            metrics.end_stage("plan")
            return ToolRunResponse(
                tool_name=request.tool_name,
                dry_run=request.dry_run,
                success=False,
                execution_ms=int(metrics.total_execution_time_ms),
                exception_message=f"Unknown tool: {request.tool_name}",
                execution_id=execution_id,
            )

        try:
            # Plan stage
            metrics.start_stage("plan")
            if request.plan_id:
                plan_record = await self.session.get(ExecutionPlanRecord, request.plan_id)
            await _set_pipeline_stage("plan")
            metrics.end_stage("plan")

            # Permission stage
            metrics.start_stage("permission")
            await _set_pipeline_stage("permission")
            try:
                self.security.validate_tool_permission(spec.permission_level, spec.permission_level)
            except PermissionError as exc:
                metrics.end_stage("permission")
                return ToolRunResponse(
                    tool_name=request.tool_name,
                    dry_run=request.dry_run,
                    success=False,
                    execution_ms=int(metrics.total_execution_time_ms),
                    exception_message=str(exc),
                    execution_id=execution_id,
                )
            metrics.end_stage("permission")

            # Workspace stage (for modifying tools)
            metrics.start_stage("workspace")
            await _set_pipeline_stage("workspace")
            if is_modifying and not workspace_id:
                repository_id = request.inputs.get("repository_id")
                if repository_id and request.plan_id:
                    ws = await self.workspace_manager.create_workspace(
                        repository_id=repository_id,
                        plan_id=request.plan_id,
                        execution_id=execution_id,
                    )
                    workspace_id = ws.id
            metrics.end_stage("workspace")

            # Checkpoint stage (for modifying tools, before write)
            metrics.start_stage("checkpoint")
            await _set_pipeline_stage("checkpoint")
            if is_modifying and not request.dry_run and spec.rollback_support and request.plan_id:
                repository_id = request.inputs.get("repository_id")
                repo_path = None
                if repository_id:
                    from backend.database.models import RepositoryRecord
                    repo_record = await self.session.get(RepositoryRecord, repository_id)
                    if repo_record:
                        repo_path = repo_record.local_path
                checkpoint_id = await self.checkpoint_engine.create_checkpoint(
                    plan_id=request.plan_id,
                    workspace_id=workspace_id,
                    repository_id=repository_id,
                    repo_path=repo_path,
                    tool_name=request.tool_name,
                    modified_files=request.inputs.get("path") if isinstance(request.inputs.get("path"), list) else [request.inputs.get("path", "")] if request.inputs.get("path") else [],
                    reasoning=request.reasoning or f"Before {request.tool_name} execution",
                    execution_id=execution_id,
                )
            metrics.end_stage("checkpoint")

            # Dry Run stage
            metrics.start_stage("dry_run")
            await _set_pipeline_stage("dry_run")
            dry_run_result = None
            if request.dry_run or is_modifying:
                dry_run_result = await self.registry.dry_run(request.tool_name, request.inputs, repository_id=request.inputs.get("repository_id"))
            metrics.end_stage("dry_run")

            # Diff stage
            metrics.start_stage("diff")
            await _set_pipeline_stage("diff")
            diff_preview = dry_run_result.diff_preview if dry_run_result else None
            affected_files = dry_run_result.affected_files if dry_run_result else []
            estimated_impact = dry_run_result.estimated_impact if dry_run_result else ""
            risks = dry_run_result.risks if dry_run_result else []
            metrics.end_stage("diff")

            # Approval stage
            metrics.start_stage("approval")
            await _set_pipeline_stage("approval")
            if is_modifying and not request.dry_run and request.plan_id:
                if plan_record and plan_record.approval_status != "approved":
                    requires_approval = True
                    metrics.end_stage("approval")
                    return ToolRunResponse(
                        tool_name=request.tool_name,
                        dry_run=True,
                        success=True,
                        execution_ms=int(metrics.total_execution_time_ms),
                        result=dry_run_result.result if dry_run_result else {},
                        affected_files=affected_files,
                        diff_preview=diff_preview,
                        estimated_impact=estimated_impact,
                        risks=risks,
                        requires_approval=True,
                        workspace_id=workspace_id,
                        execution_id=execution_id,
                    )
            metrics.end_stage("approval")

            # Execute stage
            metrics.start_stage("execute")
            await _set_pipeline_stage("execute")
            if request.dry_run:
                result = dry_run_result
                metrics.end_stage("execute")
            else:
                self._log("info", f"Executing tool: {request.tool_name}", {"execution_id": execution_id, "checkpoint_id": checkpoint_id})
                result = await self.registry.execute(request.tool_name, request.inputs)
                metrics.record_tool_execution(metrics.end_stage("execute"))

            # Validate stage
            metrics.start_stage("validate")
            await _set_pipeline_stage("validate")
            if not request.dry_run and result and result.success and affected_files:
                repo_path = None
                repository_id = request.inputs.get("repository_id")
                if repository_id:
                    from backend.database.models import RepositoryRecord
                    repo_record = await self.session.get(RepositoryRecord, repository_id)
                    if repo_record:
                        repo_path = repo_record.local_path
                if repo_path:
                    validation_results = await self.validation_engine.validate_all(repo_path, checks=["format", "lint"])
                    metrics.record_validation(metrics.end_stage("validate"))
            else:
                metrics.end_stage("validate")

            # Commit stage (for modifying tools)
            metrics.start_stage("commit")
            await _set_pipeline_stage("commit")
            if is_modifying and not request.dry_run and workspace_id:
                ws = await self.workspace_manager.get_workspace(workspace_id)
                if ws:
                    await self.workspace_manager.commit_workspace_changes(ws, f"Tool: {request.tool_name} - {request.reasoning or 'auto'}")
            metrics.end_stage("commit")

            # Update RAG stage (placeholder)
            metrics.start_stage("update_rag")
            await _set_pipeline_stage("update_rag")
            metrics.end_stage("update_rag")

            # Update Graph stage (placeholder)
            metrics.start_stage("update_graph")
            await _set_pipeline_stage("update_graph")
            metrics.end_stage("update_graph")

            # Cleanup stage
            metrics.start_stage("cleanup")
            await _set_pipeline_stage("cleanup")
            if is_modifying and not request.dry_run and workspace_id:
                ws = await self.workspace_manager.get_workspace(workspace_id)
                if ws:
                    await self.workspace_manager.destroy_workspace(ws)
            metrics.end_stage("cleanup")

            execution_ms = int(metrics.total_execution_time_ms)
            self._log("info", f"Tool completed: {request.tool_name} (success={result.success if result else True})", {"execution_id": execution_id, "success": result.success if result else True, "execution_ms": execution_ms})
            await self._save_execution(execution_id, request, result, execution_ms, success=result.success if result else True, dry_run=request.dry_run)

            if plan_record:
                plan_record.metrics_json = metrics.to_dict()
                await self.session.commit()

            return ToolRunResponse(
                tool_name=request.tool_name,
                dry_run=request.dry_run,
                success=result.success if result else True,
                execution_ms=execution_ms,
                result=result.result if result else {},
                affected_files=affected_files,
                diff_preview=diff_preview,
                estimated_impact=estimated_impact,
                risks=risks,
                requires_approval=requires_approval,
                checkpoint_id=checkpoint_id,
                workspace_id=workspace_id,
                exception_message=result.exception_message if result else "",
                execution_id=execution_id,
            )

        except Exception as exc:
            execution_ms = int(metrics.total_execution_time_ms)
            self._log("error", f"Tool failed: {request.tool_name}: {exc}", {"execution_id": execution_id})
            await self._save_execution(execution_id, request, {}, execution_ms, success=False, dry_run=request.dry_run, exception_message=str(exc))
            if plan_record:
                plan_record.metrics_json = metrics.to_dict()
                await self.session.commit()
            return ToolRunResponse(
                tool_name=request.tool_name,
                dry_run=request.dry_run,
                success=False,
                execution_ms=execution_ms,
                result={},
                exception_message=str(exc),
                requires_approval=requires_approval,
                checkpoint_id=checkpoint_id,
                workspace_id=workspace_id,
                execution_id=execution_id,
            )

    async def run_tool(self, request: ToolRunRequest) -> ToolRunResponse:
        return await self.run_full_pipeline(request)

    async def _save_execution(
        self,
        execution_id: str,
        request: ToolRunRequest,
        result: Any,
        execution_ms: int,
        *,
        success: bool,
        dry_run: bool,
        exception_message: str = "",
    ) -> None:
        record = ToolExecutionRecord(
            id=execution_id,
            plan_id=request.plan_id,
            tool_name=request.tool_name,
            input_json=request.inputs,
            output_json=result.result if hasattr(result, "result") else {},
            workspace_id=request.workspace_id,
            status="completed" if success else "failed",
            dry_run=dry_run,
            success=success,
            execution_ms=execution_ms,
            exception_message=exception_message,
            execution_id=execution_id,
        )
        self.session.add(record)
        await self.session.commit()

    def _log(self, level: str, message: str, metadata: dict[str, Any] | None = None) -> None:
        pass
