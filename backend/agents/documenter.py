from __future__ import annotations

import json
import time
from typing import Any

from backend.agents.base import AgentContext, BaseAgent
from backend.models.schemas import ToolRunRequest


class DocumentationAgent(BaseAgent):
    name = "documenter"
    description = "Updates documentation for code changes"

    async def run(self) -> AgentContext:
        started_at = time.perf_counter()
        tool_calls = 0

        changed_files: list[str] = []
        for response in self.context.tool_responses:
            affected = response.affected_files or []
            changed_files.extend(affected)

        unique_files = sorted(set(changed_files))
        doc_content = f"# Change Documentation\n\n"
        doc_content += f"## Summary\n\n"
        doc_content += f"The following files were modified during execution {self.context.execution_id}:\n\n"
        for fp in unique_files:
            doc_content += f"- `{fp}`\n"
        doc_content += f"\n## Execution Details\n\n"
        doc_content += f"- **Execution ID**: {self.context.execution_id}\n"
        if self.context.plan_id:
            doc_content += f"- **Plan ID**: {self.context.plan_id}\n"
        doc_content += f"- **Tool Responses**: {len(self.context.tool_responses)}\n"

        doc_request = ToolRunRequest(
            tool_name="CreateFile",
            inputs={
                "path": "CHANGELOG.md",
                "content": doc_content,
                "repository_id": self.context.repository_id,
            },
            plan_id=self.context.plan_id,
            dry_run=True,
            reasoning="Create or update documentation for code changes",
            execution_id=self.context.execution_id,
        )
        dry_resp = await self.dry_run_tool(doc_request)
        tool_calls += 1
        if dry_resp.success:
            doc_request.dry_run = False
            await self.use_tool(doc_request)
            tool_calls += 1

        reasoning = await self._reason(
            system_prompt="You are a Documentation agent. Update documentation for code changes. Return JSON with: reasoning (str), alternatives_considered (list), why_this_choice (str), confidence (float 0-1), expected_risks (list).",
            context_prompt=f"User request: {self.context.user_request}\nChanged files: {json.dumps(unique_files)}\nTool responses: {len(self.context.tool_responses)}",
            fallback=f"Generated documentation covering {len(unique_files)} changed file(s) from {len(self.context.tool_responses)} tool response(s).",
        )

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        await self.append_trace(
            agent_name=self.name,
            ai_reasoning=reasoning,
            input_summary=f"Changed files: {len(unique_files)}",
            output_summary=f"Documentation written to CHANGELOG.md",
            tool_calls=tool_calls,
            duration_ms=duration_ms,
            success=True,
        )

        await self._save_plan_trace()
        return self.context
