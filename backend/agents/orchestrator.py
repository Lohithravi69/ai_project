from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.base import AgentContext, BaseAgent
from backend.agents.types import AGENT_ORDER, AgentType
from backend.config import get_settings
from backend.database.models import ExecutionPlanRecord
from backend.embeddings.ollama_client import OllamaClient
from backend.learning.evaluator import SelfEvaluator
from backend.learning.experience_store import ExperienceEntry, ExperienceStore
from backend.learning.pattern_store import PatternStore
from backend.learning.repo_analytics import RepoAnalytics
from backend.models.schemas import AgentRunRequest, AgentRunResponse, AgentStatusResponse, AgentTraceEntry, AIReasoning


class AgentOrchestrator:
    def __init__(self, session: AsyncSession, max_repair_iterations: int = 3) -> None:
        self.session = session
        self.max_repair_iterations = max_repair_iterations
        settings = get_settings()
        self._ollama = OllamaClient(
            base_url=settings.ollama_base_url,
            chat_model=settings.ollama_chat_model,
            embed_model=settings.ollama_embed_model,
        )
        self._experience_store = ExperienceStore()
        self._pattern_store = PatternStore()
        self._evaluator = SelfEvaluator(self._ollama)
        self._analytics = RepoAnalytics(self._experience_store)

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

        similar = self._experience_store.search_similar(request.request_text, limit=3)
        if similar:
            context.plan["similar_experiences"] = [
                {"objective": e.objective[:200], "outcome": e.outcome}
                for e, _score in similar
            ]

        mode_agents = self._get_agents_for_mode(request.mode)

        iterator = _PipelineIterator(
            context=context,
            mode_agents=mode_agents,
            session=self.session,
            ollama=self._ollama,
            evaluator=self._evaluator,
            plan=plan,
            max_repair=self.max_repair_iterations,
        )
        await iterator.run()

        plan.agent_status = "completed"
        await self.session.commit()

        self._store_experience(context)

        report = self._generate_report(context)

        return AgentRunResponse(
            execution_id=context.execution_id,
            plan_id=context.plan_id or "",
            status="completed",
            agent_trace=context.agent_trace,
            result_summary=report,
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

    def get_experience_store(self) -> ExperienceStore:
        return self._experience_store

    def get_pattern_store(self) -> PatternStore:
        return self._pattern_store

    def get_analytics(self) -> RepoAnalytics:
        return self._analytics

    def _store_experience(self, context: AgentContext) -> None:
        outcomes = [t.success for t in context.agent_trace]
        overall = "success" if all(outcomes) and not context.errors else "failure"
        entry = ExperienceEntry(
            execution_id=context.execution_id,
            repository_id=context.repository_id,
            objective=context.user_request[:500],
            plan_summary=context.plan.get("objective", "")[:500] if context.plan else "",
            tools_used=list({
                r.tool_name for r in context.current_tool_requests
            }),
            failures=context.errors,
            fixes=[],
            duration_ms=sum(t.duration_ms for t in context.agent_trace),
            outcome=overall,
        )
        self._experience_store.store(entry)

    def _generate_report(self, context: AgentContext) -> str:
        parts: list[str] = []
        total_tools = len(context.current_tool_requests)
        total_errors = len(context.errors)
        total_traces = len(context.agent_trace)

        parts.append(f"Execution {context.execution_id[:8]}: {total_traces} agents, {total_tools} tool calls")
        if total_errors:
            parts.append(f"{total_errors} error(s)")
        else:
            parts.append("no errors")

        failed_traces = [t for t in context.agent_trace if not t.success]
        if failed_traces:
            parts.append("failed agents: " + ", ".join(t.agent_name for t in failed_traces))

        return " | ".join(parts)

    def _get_agents_for_mode(self, mode: str) -> list[AgentType]:
        if mode == "plan-only":
            return [AgentType.PLANNER]
        if mode == "code-only":
            return [AgentType.CODER, AgentType.REVIEWER, AgentType.TESTER, AgentType.DOCUMENTER]
        return AGENT_ORDER

    def _create_agent(self, agent_type: AgentType, context: AgentContext) -> BaseAgent | None:
        try:
            if agent_type == AgentType.PLANNER:
                from backend.agents.planner import PlannerAgent
                return PlannerAgent(self.session, context, self._ollama)
            elif agent_type == AgentType.ARCHITECT:
                from backend.agents.architect import ArchitectAgent
                return ArchitectAgent(self.session, context, self._ollama)
            elif agent_type == AgentType.DECOMPOSER:
                from backend.agents.decomposer import TaskDecomposerAgent
                return TaskDecomposerAgent(self.session, context, self._ollama)
            elif agent_type == AgentType.CODER:
                from backend.agents.coder import CodingAgent
                return CodingAgent(self.session, context, self._ollama)
            elif agent_type == AgentType.REVIEWER:
                from backend.agents.reviewer import ReviewerAgent
                return ReviewerAgent(self.session, context, self._ollama)
            elif agent_type == AgentType.TESTER:
                from backend.agents.tester import TestingAgent
                return TestingAgent(self.session, context, self._ollama)
            elif agent_type == AgentType.DEBUGGER:
                from backend.agents.debugger import DebugAgent
                return DebugAgent(self.session, context, self._ollama)
            elif agent_type == AgentType.DOCUMENTER:
                from backend.agents.documenter import DocumentationAgent
                return DocumentationAgent(self.session, context, self._ollama)
        except ImportError:
            return None
        return None


class _PipelineIterator:
    def __init__(
        self,
        context: AgentContext,
        mode_agents: list[AgentType],
        session: AsyncSession,
        ollama: OllamaClient | None,
        evaluator: SelfEvaluator,
        plan: ExecutionPlanRecord,
        max_repair: int = 3,
    ) -> None:
        self._context = context
        self._mode_agents = mode_agents
        self._session = session
        self._ollama = ollama
        self._evaluator = evaluator
        self._plan = plan
        self._max_repair = max_repair
        self._full_cycle = [
            AgentType.CODER,
            AgentType.REVIEWER,
            AgentType.TESTER,
        ]

    async def run(self) -> None:
        idx = 0
        while idx < len(self._mode_agents):
            agent_type = self._mode_agents[idx]
            if agent_type in self._full_cycle and self._has_repair_loop(agent_type):
                remaining = self._mode_agents[idx:]
                repair_count = sum(1 for t in remaining if t == agent_type)
                if repair_count <= 1:
                    await self._run_repair_loop()
                    idx = self._skip_past_test(idx)
                    continue
            agent = self._create_agent(agent_type)
            if agent:
                await self._run_agent(agent, agent_type)
            idx += 1

    def _has_repair_loop(self, agent_type: AgentType) -> bool:
        has_coder = AgentType.CODER in self._mode_agents
        has_tester = AgentType.TESTER in self._mode_agents
        return has_coder and has_tester and agent_type in (AgentType.CODER, AgentType.REVIEWER)

    def _skip_past_test(self, current_idx: int) -> int:
        for i in range(current_idx, len(self._mode_agents)):
            if self._mode_agents[i] == AgentType.TESTER:
                return i + 1
        return len(self._mode_agents)

    async def _run_repair_loop(self) -> None:
        for iteration in range(1, self._max_repair + 1):
            coder = self._create_agent(AgentType.CODER)
            if not coder:
                return
            await self._run_agent(coder, AgentType.CODER)

            reviewer = self._create_agent(AgentType.REVIEWER)
            if reviewer:
                await self._run_agent(reviewer, AgentType.REVIEWER)

            tester = self._create_agent(AgentType.TESTER)
            if not tester:
                return
            await self._run_agent(tester, AgentType.TESTER)

            eval_result = await self._evaluator.evaluate(
                user_request=self._context.user_request,
                tool_requests=self._context.current_tool_requests,
                tool_responses=self._context.tool_responses,
                errors=self._context.errors,
            )

            self._context.agent_trace.append(AgentTraceEntry(
                agent_name="evaluator",
                started_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                input_summary=f"Repair iteration {iteration}/{self._max_repair}",
                output_summary=eval_result.summary,
                ai_reasoning=AIReasoning(
                    reasoning=eval_result.summary,
                    confidence=eval_result.score,
                ),
                success=eval_result.passed,
            ))

            if eval_result.passed:
                return

            if iteration < self._max_repair:
                debugger = self._create_agent(AgentType.DEBUGGER)
                if debugger:
                    await self._run_agent(debugger, AgentType.DEBUGGER)
                    self._context.errors.append(
                        f"Repair iteration {iteration}: analyzing and retrying"
                    )

    async def _run_agent(self, agent: BaseAgent, agent_type: AgentType) -> None:
        try:
            self._plan.agent_status = f"running:{agent_type.value}"
            await self._session.commit()
            await agent.run()
        except Exception as exc:
            await agent.append_trace(
                agent_name=agent.name,
                ai_reasoning=AIReasoning(reasoning=f"Agent failed: {exc}"),
                success=False,
                error=str(exc),
            )

    def _create_agent(self, agent_type: AgentType) -> BaseAgent | None:
        try:
            from backend.agents.planner import PlannerAgent
            from backend.agents.architect import ArchitectAgent
            from backend.agents.decomposer import TaskDecomposerAgent
            from backend.agents.coder import CodingAgent
            from backend.agents.reviewer import ReviewerAgent
            from backend.agents.tester import TestingAgent
            from backend.agents.debugger import DebugAgent
            from backend.agents.documenter import DocumentationAgent

            mapping = {
                AgentType.PLANNER: PlannerAgent,
                AgentType.ARCHITECT: ArchitectAgent,
                AgentType.DECOMPOSER: TaskDecomposerAgent,
                AgentType.CODER: CodingAgent,
                AgentType.REVIEWER: ReviewerAgent,
                AgentType.TESTER: TestingAgent,
                AgentType.DEBUGGER: DebugAgent,
                AgentType.DOCUMENTER: DocumentationAgent,
            }
            cls = mapping.get(agent_type)
            if cls:
                return cls(self._session, self._context, self._ollama)
        except ImportError:
            return None
        return None
