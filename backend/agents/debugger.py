from __future__ import annotations

import json
import time
from typing import Any

from backend.agents.base import AgentContext, BaseAgent


class DebugAgent(BaseAgent):
    name = "debugger"
    description = "Analyzes test failures and suggests fixes"

    async def run(self) -> AgentContext:
        started_at = time.perf_counter()

        test_responses = [r for r in self.context.tool_responses if r.tool_name == "RunPyTest"]
        failure_analysis: list[dict[str, Any]] = []

        for response in test_responses:
            if response.success:
                continue

            result = response.result or {}
            output = result.get("output", result.get("stdout", ""))
            failure_analysis.append({
                "tool_response": response.tool_name,
                "success": response.success,
                "exception": response.exception_message,
                "output_snippet": output[:500],
                "root_cause": "Test failure detected - review output for specific assertion errors",
                "suggested_fix": "Check modified code for regressions and verify test expectations.",
            })

        if not failure_analysis:
            failure_analysis.append({
                "tool_response": "all",
                "success": True,
                "exception": "",
                "output_snippet": "",
                "root_cause": "No test failures detected",
                "suggested_fix": "",
            })

        reasoning = await self._reason(
            system_prompt="You are a Debug agent. Analyze test failures and suggest fixes. Return JSON with: reasoning (str), alternatives_considered (list), why_this_choice (str), confidence (float 0-1), expected_risks (list).",
            context_prompt=f"User request: {self.context.user_request}\nTest responses: {len(test_responses)}\nFailure analysis: {json.dumps(failure_analysis, indent=2)}",
            fallback=f"Analyzed {len(test_responses)} test run(s) and produced {len(failure_analysis)} failure analysis entries.",
        )

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        await self.append_trace(
            agent_name=self.name,
            ai_reasoning=reasoning,
            input_summary=f"Test responses: {len(test_responses)}",
            output_summary=f"Failure analyses: {len(failure_analysis)}",
            tool_calls=0,
            duration_ms=duration_ms,
            success=True,
        )

        await self._save_plan_trace()
        return self.context
