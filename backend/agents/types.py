from __future__ import annotations

from enum import Enum


class AgentType(str, Enum):
    PLANNER = "planner"
    ARCHITECT = "architect"
    DECOMPOSER = "decomposer"
    CODER = "coder"
    REVIEWER = "reviewer"
    TESTER = "tester"
    DEBUGGER = "debugger"
    DOCUMENTER = "documenter"
    ORCHESTRATOR = "orchestrator"


AGENT_ORDER: list[AgentType] = [
    AgentType.PLANNER,
    AgentType.ARCHITECT,
    AgentType.DECOMPOSER,
    AgentType.CODER,
    AgentType.REVIEWER,
    AgentType.TESTER,
    AgentType.DEBUGGER,
    AgentType.DOCUMENTER,
]
