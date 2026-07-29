from __future__ import annotations

import time
from typing import Any

from backend.agents.base import AgentContext, BaseAgent


class ReviewerAgent(BaseAgent):
    name = "reviewer"
    description = "Reviews code changes for quality, security, and correctness"

    async def run(self) -> AgentContext:
        started_at = time.perf_counter()

        feedback: list[dict[str, Any]] = []
        for response in self.context.tool_responses:
            if not response.success:
                feedback.append({
                    "file": "",
                    "line": 0,
                    "severity": "error",
                    "message": f"Tool {response.tool_name} failed: {response.exception_message}",
                    "suggestion": "Check tool inputs and retry execution.",
                })
                continue

            affected = response.affected_files or []
            for file_path in affected:
                feedback.append({
                    "file": file_path,
                    "line": 0,
                    "severity": "info",
                    "message": f"Modified by {response.tool_name}",
                    "suggestion": "Verify changes are consistent with project conventions.",
                })

            risks = response.risks or []
            for risk in risks:
                feedback.append({
                    "file": "",
                    "line": 0,
                    "severity": "warning",
                    "message": f"Risk detected: {risk}",
                    "suggestion": "Review risk area and confirm acceptable.",
                })

        self.context.review_feedback = feedback

        reasoning = self.record_reasoning(
            reasoning=f"Reviewed {len(self.context.tool_responses)} tool responses and produced {len(feedback)} feedback entries.",
            alternatives_considered=["Skip review for successful tools", "Only flag errors"],
            why_this_choice="Reviews all responses for errors, affected files, and risks to ensure quality.",
            confidence=0.85,
            risks=["Review may miss semantic issues not captured by tool metadata"],
        )

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        await self.append_trace(
            agent_name=self.name,
            ai_reasoning=reasoning,
            input_summary=f"Tool responses: {len(self.context.tool_responses)}",
            output_summary=f"Feedback entries: {len(feedback)}",
            tool_calls=0,
            duration_ms=duration_ms,
            success=True,
        )

        await self._save_plan_trace()
        return self.context
