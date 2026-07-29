from __future__ import annotations

import time
from typing import Any

from backend.agents.base import AgentContext, BaseAgent


class ArchitectAgent(BaseAgent):
    name = "architect"
    description = "Produces technical design from the high-level plan"

    async def run(self) -> AgentContext:
        started_at = time.perf_counter()

        plan = self.context.plan
        required_tools = plan.get("required_tools", [])
        modifying = plan.get("modifying", False)

        files_to_modify = []
        if modifying:
            for tool in required_tools:
                if tool in ("WriteFile", "CreateFile", "DeleteFile", "MoveFile"):
                    files_to_modify.append(f"target_{tool.lower()}_path")

        design: dict[str, Any] = {
            "components": [
                {
                    "name": "entry_point",
                    "type": "module",
                    "description": "Primary module to be modified or created",
                    "tools_required": [t for t in required_tools if t in ("ReadFile", "WriteFile", "CreateFile")],
                }
            ],
            "data_flow": {
                "input": self.context.user_request,
                "processing": "Tool-based execution through Phase 3 Tool Layer",
                "output": "Modified files and execution results",
            },
            "files_to_modify": files_to_modify,
            "interfaces": [
                {
                    "name": "tool_api",
                    "type": "Phase 3 Tool Layer",
                    "description": "All changes route through the tool registry",
                }
            ],
            "dependencies": [
                {
                    "name": tool,
                    "source": "tool_registry",
                }
                for tool in required_tools
            ],
        }

        self.context.architecture = design

        reasoning = self.record_reasoning(
            reasoning=f"Produced technical architecture with {len(design['components'])} component(s) and {len(design['dependencies'])} dependency(ies).",
            alternatives_considered=["Minimal single-component design", "Full multi-component decomposition"],
            why_this_choice="Architecture reflects the required tools and modifying vs read-only nature of the plan.",
            confidence=0.85,
            risks=["Architecture may miss implicit dependencies not captured in tool list"],
        )

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        await self.append_trace(
            agent_name=self.name,
            ai_reasoning=reasoning,
            input_summary=f"Plan: {self.context.plan.get('plan_id', '')}",
            output_summary=f"Architecture: {len(design['components'])} components, {len(design['dependencies'])} dependencies",
            tool_calls=0,
            duration_ms=duration_ms,
            success=True,
        )

        await self._save_plan_trace()
        return self.context
