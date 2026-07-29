from __future__ import annotations

import json
import time
from typing import Any

from backend.agents.base import AgentContext, BaseAgent
from backend.models.schemas import ToolRunRequest


class CodingAgent(BaseAgent):
    name = "coder"
    description = "Implements code changes using Phase 3 tools"

    async def run(self) -> AgentContext:
        started_at = time.perf_counter()
        tool_calls = 0
        errors: list[str] = []

        for task in self.context.tasks:
            if task.get("tool_name") in ("ReadFile", "SearchRepository", "ListFiles", "GitStatus", "GitDiff", "QueryVectorStore", "QueryPostgres", "ReadLogs"):
                continue

            request = ToolRunRequest(
                tool_name=task["tool_name"],
                inputs=task.get("inputs", {}),
                plan_id=self.context.plan_id,
                workspace_id=None,
                dry_run=True,
                reasoning=task.get("reasoning", ""),
                execution_id=self.context.execution_id,
            )

            dry_response = await self.dry_run_tool(request)
            tool_calls += 1

            if not dry_response.success:
                errors.append(f"Dry run failed for {task['tool_name']}: {dry_response.exception_message}")
                continue

            request.dry_run = False
            execute_response = await self.use_tool(request)
            tool_calls += 1

            if not execute_response.success:
                errors.append(f"Execution failed for {task['tool_name']}: {execute_response.exception_message}")

        self.context.errors = errors

        reasoning = await self._reason(
            system_prompt="You are a Coding agent. Implement code changes using Phase 3 tools with dry-run-first safety. Return JSON with: reasoning (str), alternatives_considered (list), why_this_choice (str), confidence (float 0-1), expected_risks (list).",
            context_prompt=f"User request: {self.context.user_request}\nTasks: {json.dumps(self.context.tasks)}\nTool calls: {tool_calls}\nErrors: {errors}",
            fallback=f"Executed {len(self.context.tasks)} tasks with {tool_calls} total tool calls ({'success' if not errors else 'with errors'}).",
        )

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        await self.append_trace(
            agent_name=self.name,
            ai_reasoning=reasoning,
            input_summary=f"Tasks: {len(self.context.tasks)}",
            output_summary=f"Tool calls: {tool_calls}, errors: {len(errors)}",
            tool_calls=tool_calls,
            duration_ms=duration_ms,
            success=len(errors) == 0,
            error="; ".join(errors) if errors else "",
        )

        await self._save_plan_trace()
        return self.context
