from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.base import AgentContext, BaseAgent
from backend.agents.types import AGENT_ORDER, AgentType
from backend.database.models import ExecutionPlanRecord
from backend.models.schemas import AgentRunRequest, AgentRunResponse, AgentStatusResponse, AgentTraceEntry, AIReasoning


class AgentOrchestrator:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run_full_pipeline(self, request: AgentRunRequest) -> AgentRunResponse:
        context = AgentContext()
        context.user_request = request.request_text
        context.repository_id = request.repository_id
        context.mode = request.mode

        plan = ExecutionPlanRecord(
            objective=request.request_text[:500],
            reasoning=request.request_text,
            agent_status="running",
        )
        self.session.add(plan)
        await self.session.commit()
        await self.session.refresh(plan)
        context.plan_id = plan.id
        plan.execution_id = context.execution_id

        mode_agents = self._get_agents_for_mode(request.mode)
        for agent_type in mode_agents:
            agent = self._create_agent(agent_type, context)
            if agent:
                try:
                    plan.agent_status = f"running:{agent_type.value}"
                    await self.session.commit()
                    await agent.run()
                except Exception as exc:
                    await agent.append_trace(
                        agent_name=agent.name,
                        ai_reasoning=AIReasoning(reasoning=f"Agent failed: {exc}"),
                        success=False,
                        error=str(exc),
                    )

        plan.agent_status = "completed"
        await self.session.commit()

        return AgentRunResponse(
            execution_id=context.execution_id,
            plan_id=context.plan_id or "",
            status="completed",
            agent_trace=context.agent_trace,
            result_summary=f"Pipeline completed with {len(context.tool_responses)} tool calls",
        )

    async def get_status(self, execution_id: str) -> AgentStatusResponse | None:
        from sqlalchemy import select

        result = await self.session.execute(
            select(ExecutionPlanRecord).where(ExecutionPlanRecord.execution_id == execution_id)
        )
        plan = result.scalar_one_or_none()
        if not plan:
            return None
        return AgentStatusResponse(
            execution_id=execution_id,
            plan_id=plan.id,
            agent_status=plan.agent_status,
            current_agent=plan.agent_status.replace("running:", "") if plan.agent_status.startswith("running:") else "",
            progress=plan.agent_status,
        )

    async def get_trace(self, plan_id: str) -> list[AgentTraceEntry]:
        plan = await self.session.get(ExecutionPlanRecord, plan_id)
        if not plan:
            return []
        return [AgentTraceEntry(**t) for t in plan.agent_trace_json or []]

    def _get_agents_for_mode(self, mode: str) -> list[AgentType]:
        if mode == "plan-only":
            return [AgentType.PLANNER]
        if mode == "code-only":
            return [AgentType.CODER, AgentType.REVIEWER, AgentType.TESTER]
        return AGENT_ORDER

    def _create_agent(self, agent_type: AgentType, context: AgentContext) -> BaseAgent | None:
        try:
            if agent_type == AgentType.PLANNER:
                from backend.agents.planner import PlannerAgent

                return PlannerAgent(self.session, context)
            elif agent_type == AgentType.ARCHITECT:
                from backend.agents.architect import ArchitectAgent

                return ArchitectAgent(self.session, context)
            elif agent_type == AgentType.DECOMPOSER:
                from backend.agents.decomposer import TaskDecomposerAgent

                return TaskDecomposerAgent(self.session, context)
            elif agent_type == AgentType.CODER:
                from backend.agents.coder import CodingAgent

                return CodingAgent(self.session, context)
            elif agent_type == AgentType.REVIEWER:
                from backend.agents.reviewer import ReviewerAgent

                return ReviewerAgent(self.session, context)
            elif agent_type == AgentType.TESTER:
                from backend.agents.tester import TestingAgent

                return TestingAgent(self.session, context)
            elif agent_type == AgentType.DEBUGGER:
                from backend.agents.debugger import DebugAgent

                return DebugAgent(self.session, context)
            elif agent_type == AgentType.DOCUMENTER:
                from backend.agents.documenter import DocumentationAgent

                return DocumentationAgent(self.session, context)
        except ImportError:
            return None
        return None
