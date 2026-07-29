from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import ExecutionPlanRecord
from backend.execution.execution_manager import ExecutionManager
from backend.execution.metrics import MetricsCollector
from backend.models.schemas import (
    AIReasoning,
    AgentTraceEntry,
    ToolRunRequest,
    ToolRunResponse,
)
from backend.tool_registry.registry import ToolRegistry


class AgentContext:
    def __init__(
        self,
        execution_id: str | None = None,
        plan_id: str | None = None,
    ) -> None:
        self.execution_id: str = execution_id or str(uuid4())
        self.plan_id: str | None = plan_id
        self.user_request: str = ""
        self.plan: dict[str, Any] = {}
        self.architecture: dict[str, Any] = {}
        self.tasks: list[dict[str, Any]] = []
        self.current_tool_requests: list[ToolRunRequest] = []
        self.tool_responses: list[ToolRunResponse] = []
        self.review_feedback: list[dict[str, Any]] = []
        self.agent_trace: list[AgentTraceEntry] = []
        self.errors: list[str] = []
        self.repository_id: str = ""
        self.mode: str = "full"


class BaseAgent(ABC):
    name: str = ""
    description: str = ""

    def __init__(self, session: AsyncSession, context: AgentContext, ollama_client: Any = None) -> None:
        self.session = session
        self.context = context
        self.registry = ToolRegistry()
        self.execution_manager = ExecutionManager(session)
        self.metrics = MetricsCollector()
        self._ollama = ollama_client
        self._started_at: float = 0.0

    @abstractmethod
    async def run(self) -> AgentContext:
        ...

    async def _reason(
        self,
        system_prompt: str,
        context_prompt: str,
        fallback: str = "",
    ) -> AIReasoning:
        if self._ollama is None:
            return self.record_reasoning(reasoning=fallback)
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context_prompt},
            ]
            content = await asyncio.wait_for(
                self._ollama.chat(messages),
                timeout=8.0,
            )
            data = json.loads(content)
            return AIReasoning(
                reasoning=data.get("reasoning", fallback),
                alternatives_considered=data.get("alternatives_considered", []),
                why_this_choice=data.get("why_this_choice", ""),
                confidence=float(data.get("confidence", 0.0)),
                expected_risks=data.get("expected_risks", []),
            )
        except Exception:
            return self.record_reasoning(reasoning=fallback)

    async def use_tool(self, request: ToolRunRequest) -> ToolRunResponse:
        request.execution_id = self.context.execution_id
        response = await self.execution_manager.run_tool(request)
        self.context.current_tool_requests.append(request)
        self.context.tool_responses.append(response)
        return response

    async def dry_run_tool(self, request: ToolRunRequest) -> ToolRunResponse:
        request.dry_run = True
        return await self.use_tool(request)

    def record_reasoning(
        self,
        reasoning: str,
        alternatives: list[str] | None = None,
        why: str = "",
        confidence: float = 0.0,
        risks: list[str] | None = None,
    ) -> AIReasoning:
        return AIReasoning(
            reasoning=reasoning,
            alternatives_considered=alternatives or [],
            why_this_choice=why,
            confidence=confidence,
            expected_risks=risks or [],
        )

    async def append_trace(
        self,
        agent_name: str,
        ai_reasoning: AIReasoning,
        *,
        input_summary: str = "",
        output_summary: str = "",
        tool_calls: int = 0,
        duration_ms: int = 0,
        success: bool = True,
        error: str = "",
    ) -> None:
        entry = AgentTraceEntry(
            agent_name=agent_name,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            input_summary=input_summary,
            output_summary=output_summary,
            tool_calls=tool_calls,
            ai_reasoning=ai_reasoning,
            duration_ms=duration_ms,
            success=success,
            error=error,
        )
        self.context.agent_trace.append(entry)

    async def _save_plan_trace(self) -> None:
        if not self.context.plan_id:
            return
        plan = await self.session.get(ExecutionPlanRecord, self.context.plan_id)
        if not plan:
            return
        plan.agent_trace_json = [
            {
                "agent_name": e.agent_name,
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "finished_at": e.finished_at.isoformat() if e.finished_at else None,
                "input_summary": e.input_summary,
                "output_summary": e.output_summary,
                "tool_calls": e.tool_calls,
                "ai_reasoning": e.ai_reasoning.model_dump(),
                "duration_ms": e.duration_ms,
                "success": e.success,
                "error": e.error,
            }
            for e in self.context.agent_trace
        ]
        plan.architecture_json = self.context.architecture
        plan.agent_status = "completed"

        trace_ai = next(
            (e.ai_reasoning for e in reversed(self.context.agent_trace) if e.ai_reasoning.reasoning),
            None,
        )
        if trace_ai:
            plan.ai_reasoning_json = trace_ai.model_dump()

        if self.context.tasks:
            plan.execution_order_json = self.context.tasks

        await self.session.commit()
