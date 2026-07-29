from __future__ import annotations

from datetime import datetime, timezone

from backend.agents.base import AgentContext
from backend.agents.types import AGENT_ORDER, AgentType
from backend.models.schemas import AIReasoning, AgentTraceEntry


class TestAgentType:
    def test_has_all_nine_members(self):
        assert len(AgentType) == 9
        expected = {
            AgentType.PLANNER,
            AgentType.ARCHITECT,
            AgentType.DECOMPOSER,
            AgentType.CODER,
            AgentType.REVIEWER,
            AgentType.TESTER,
            AgentType.DEBUGGER,
            AgentType.DOCUMENTER,
            AgentType.ORCHESTRATOR,
        }
        assert set(AgentType) == expected


class TestAgentOrder:
    def test_has_eight_items(self):
        assert len(AGENT_ORDER) == 8

    def test_sequence_is_correct(self):
        expected = [
            AgentType.PLANNER,
            AgentType.ARCHITECT,
            AgentType.DECOMPOSER,
            AgentType.CODER,
            AgentType.REVIEWER,
            AgentType.TESTER,
            AgentType.DEBUGGER,
            AgentType.DOCUMENTER,
        ]
        assert AGENT_ORDER == expected

    def test_does_not_include_orchestrator(self):
        assert AgentType.ORCHESTRATOR not in AGENT_ORDER


class TestAgentContext:
    def test_initializes_with_defaults(self):
        ctx = AgentContext()
        assert ctx.execution_id is not None
        assert len(ctx.execution_id) > 0
        assert ctx.plan_id is None
        assert ctx.user_request == ""
        assert ctx.plan == {}
        assert ctx.architecture == {}
        assert ctx.tasks == []
        assert ctx.current_tool_requests == []
        assert ctx.tool_responses == []
        assert ctx.review_feedback == []
        assert ctx.agent_trace == []
        assert ctx.errors == []
        assert ctx.repository_id == ""
        assert ctx.mode == "full"

    def test_custom_execution_id(self):
        ctx = AgentContext(execution_id="custom-id")
        assert ctx.execution_id == "custom-id"

    def test_custom_plan_id(self):
        ctx = AgentContext(plan_id="plan-123")
        assert ctx.plan_id == "plan-123"


class TestAgentTraceEntrySchema:
    def test_defaults(self):
        entry = AgentTraceEntry()
        assert entry.agent_name == ""
        assert entry.started_at is None
        assert entry.finished_at is None
        assert entry.input_summary == ""
        assert entry.output_summary == ""
        assert entry.tool_calls == 0
        assert isinstance(entry.ai_reasoning, AIReasoning)
        assert entry.duration_ms == 0
        assert entry.success is True
        assert entry.error == ""

    def test_full_construction(self):
        now = datetime.now(timezone.utc)
        entry = AgentTraceEntry(
            agent_name="planner",
            started_at=now,
            finished_at=now,
            input_summary="test input",
            output_summary="test output",
            tool_calls=3,
            ai_reasoning=AIReasoning(reasoning="test"),
            duration_ms=150,
            success=True,
            error="",
        )
        assert entry.agent_name == "planner"
        assert entry.started_at == now
        assert entry.tool_calls == 3
        assert entry.duration_ms == 150


class TestAIReasoningSchema:
    def test_defaults(self):
        r = AIReasoning()
        assert r.reasoning == ""
        assert r.alternatives_considered == []
        assert r.why_this_choice == ""
        assert r.confidence == 0.0
        assert r.expected_risks == []

    def test_full_construction(self):
        r = AIReasoning(
            reasoning="Because X",
            alternatives_considered=["Y", "Z"],
            why_this_choice="X is faster",
            confidence=0.95,
            expected_risks=["Edge case A"],
        )
        assert r.reasoning == "Because X"
        assert len(r.alternatives_considered) == 2
        assert r.confidence == 0.95
        assert r.expected_risks == ["Edge case A"]
