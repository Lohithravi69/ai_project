from __future__ import annotations

import json
import time
from typing import Any

from backend.agents.base import AgentContext, BaseAgent


class TaskDecomposerAgent(BaseAgent):
    name = "decomposer"
    description = "Breaks architecture into ordered tool execution requests"

    async def run(self) -> AgentContext:
        started_at = time.perf_counter()

        architecture = self.context.architecture
        plan = self.context.plan
        required_tools = plan.get("required_tools", [])

        tasks: list[dict[str, Any]] = []
        order = 0

        for tool_name in required_tools:
            order += 1
            task: dict[str, Any] = {
                "order": order,
                "tool_name": tool_name,
                "inputs": {
                    "repository_id": self.context.repository_id,
                },
                "description": f"Execute {tool_name} to fulfill the plan",
                "reasoning": f"Required tool {tool_name} selected during planning phase",
            }
            if tool_name in ("ReadFile", "WriteFile", "CreateFile", "DeleteFile", "MoveFile"):
                task["inputs"]["path"] = ""
            if tool_name == "RunPyTest":
                task["inputs"]["test_path"] = ""
            if tool_name == "RunShellRestricted":
                task["inputs"]["command"] = ""
            if tool_name in ("CreateBranch", "CheckoutBranch"):
                task["inputs"]["branch_name"] = ""
            if tool_name == "CommitChanges":
                task["inputs"]["message"] = ""
            if tool_name == "RollbackCommit":
                task["inputs"]["checkpoint_id"] = ""
            if tool_name == "FormatCode":
                task["inputs"]["path"] = ""
            tasks.append(task)

        self.context.tasks = tasks

        reasoning = await self._reason(
            system_prompt="You are a Task Decomposer agent. Break architectural designs into ordered tool execution tasks. Return JSON with: reasoning (str), alternatives_considered (list), why_this_choice (str), confidence (float 0-1), expected_risks (list).",
            context_prompt=f"User request: {self.context.user_request}\nArchitecture: {json.dumps(architecture, indent=2)}\nTasks: {json.dumps(tasks, indent=2)}",
            fallback=f"Decomposed architecture into {len(tasks)} ordered tool execution tasks.",
        )

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        await self.append_trace(
            agent_name=self.name,
            ai_reasoning=reasoning,
            input_summary=f"Architecture: {len(architecture.get('components', []))} components",
            output_summary=f"Tasks: {len(tasks)} total",
            tool_calls=0,
            duration_ms=duration_ms,
            success=True,
        )

        await self._save_plan_trace()
        return self.context
