from __future__ import annotations

import json
import time
from typing import Any

from backend.agents.base import AgentContext, BaseAgent
from backend.models.schemas import ToolRunRequest


class TestingAgent(BaseAgent):
    name = "tester"
    description = "Creates and runs tests for code changes"

    async def run(self) -> AgentContext:
        started_at = time.perf_counter()
        tool_calls = 0
        test_results: dict[str, Any] = {}

        test_path = ""
        for response in self.context.tool_responses:
            affected = response.affected_files or []
            for fp in affected:
                if fp.endswith(".py"):
                    test_path = fp.replace(".py", "_test.py")
                    break
            if test_path:
                break

        if test_path:
            create_request = ToolRunRequest(
                tool_name="CreateFile",
                inputs={
                    "path": test_path,
                    "content": f"# Tests for {test_path.replace('_test.py', '.py')}\n",
                    "repository_id": self.context.repository_id,
                },
                plan_id=self.context.plan_id,
                dry_run=True,
                reasoning="Create test file for modified code",
                execution_id=self.context.execution_id,
            )
            dry_resp = await self.dry_run_tool(create_request)
            tool_calls += 1
            if dry_resp.success:
                create_request.dry_run = False
                await self.use_tool(create_request)
                tool_calls += 1

        run_request = ToolRunRequest(
            tool_name="RunPyTest",
            inputs={
                "test_path": test_path or "tests/",
                "repository_id": self.context.repository_id,
            },
            plan_id=self.context.plan_id,
            dry_run=True,
            reasoning="Run tests to validate code changes",
            execution_id=self.context.execution_id,
        )
        dry_resp = await self.dry_run_tool(run_request)
        tool_calls += 1
        if dry_resp.success:
            run_request.dry_run = False
            pytest_resp = await self.use_tool(run_request)
            tool_calls += 1
            test_results = pytest_resp.result
        else:
            test_results = {"error": dry_resp.exception_message}

        reasoning = await self._reason(
            system_prompt="You are a Testing agent. Create and run tests for code changes. Return JSON with: reasoning (str), alternatives_considered (list), why_this_choice (str), confidence (float 0-1), expected_risks (list).",
            context_prompt=f"User request: {self.context.user_request}\nTest path: {test_path or 'default'}\nTool calls: {tool_calls}\nTest results: {json.dumps(test_results)}",
            fallback=f"Created test file at {test_path or 'default path'} and ran pytest. Tool calls: {tool_calls}.",
        )

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        await self.append_trace(
            agent_name=self.name,
            ai_reasoning=reasoning,
            input_summary=f"Affected files from {len(self.context.tool_responses)} responses",
            output_summary=f"Test results: {test_results.get('summary', 'completed')}",
            tool_calls=tool_calls,
            duration_ms=duration_ms,
            success=not test_results.get("error"),
            error=test_results.get("error", ""),
        )

        await self._save_plan_trace()
        return self.context
