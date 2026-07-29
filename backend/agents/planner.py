from __future__ import annotations

import json
import time
from typing import Any
from uuid import uuid4

from backend.agents.base import AgentContext, BaseAgent
from backend.database.models import ExecutionPlanRecord
from backend.learning.experience_store import ExperienceStore
from backend.learning.pattern_store import PatternStore
from backend.models.schemas import AIReasoning


class PlannerAgent(BaseAgent):
    name = "planner"
    description = "Analyzes user request and creates a structured execution plan"

    async def run(self) -> AgentContext:
        started_at = time.perf_counter()

        experience_store = ExperienceStore()
        pattern_store = PatternStore()
        similar = experience_store.search_similar(self.context.user_request, limit=3)
        matching_patterns = pattern_store.search_patterns(self.context.user_request)

        if similar:
            self.context.plan["similar_experiences"] = [
                {"objective": e.objective[:200], "outcome": e.outcome}
                for e, _score in similar
            ]
        if matching_patterns:
            self.context.plan["applicable_patterns"] = [
                {"name": p.name, "category": p.category}
                for p in matching_patterns
            ]

        text_blob = self.context.user_request.lower()
        modifying = any(kw in text_blob for kw in ["write", "edit", "update", "create", "delete", "remove", "refactor", "implement", "patch", "commit", "rollback", "move"])

        all_tools = self.registry.list_tool_names()
        required_tools = ["ReadFile", "SearchRepository", "ListFiles", "GitStatus"]
        if modifying:
            required_tools.extend(["GitDiff", "CreateBranch", "CheckoutBranch", "WriteFile", "CreateFile", "DeleteFile", "MoveFile", "FormatCode", "RunPyTest", "CommitChanges", "RollbackCommit"])
        else:
            required_tools.extend(["GitDiff", "QueryVectorStore", "QueryPostgres"])

        if "test" in text_blob and "RunPyTest" not in required_tools:
            required_tools.append("RunPyTest")
        if "shell" in text_blob and "RunShellRestricted" not in required_tools:
            required_tools.append("RunShellRestricted")
        if "format" in text_blob and "FormatCode" not in required_tools:
            required_tools.append("FormatCode")

        required_tools = [t for t in required_tools if t in all_tools]

        risk_keywords = ["delete", "rollback", "overwrite", "migrate", "destroy"]
        risk = "high" if any(kw in text_blob for kw in risk_keywords) and modifying else "medium" if modifying else "low"

        execution_order = [
            {"order": 1, "title": "Intent Analysis", "description": "Clarify objective and determine whether the request modifies files.", "tools": [], "dry_run": True},
            {"order": 2, "title": "Task Breakdown", "description": "Identify affected repositories and files.", "tools": ["ReadFile", "SearchRepository", "ListFiles"], "dry_run": True},
            {"order": 3, "title": "Tool Selection", "description": "Select the minimal tool set needed for the request.", "tools": required_tools, "dry_run": True},
            {"order": 4, "title": "Dry Run Preview", "description": "Preview the proposed change before execution.", "tools": [t for t in required_tools if t not in {"QueryVectorStore", "QueryPostgres"}], "dry_run": True},
            {"order": 5, "title": "Risk Assessment", "description": f"Estimated risk: {risk}.", "tools": [], "dry_run": True},
            {"order": 6, "title": "Approval", "description": "Modifying actions require explicit human approval.", "tools": ["RollbackCommit"], "dry_run": True},
        ]

        reasoning = await self._reason(
            system_prompt="You are a Planner agent. Analyze user requests and produce structured execution plans. Return JSON with: reasoning (str), alternatives_considered (list), why_this_choice (str), confidence (float 0-1), expected_risks (list).",
            context_prompt=f"User request: {self.context.user_request}\nModifying: {modifying}\nRisk level: {risk}\nRequired tools: {required_tools}",
            fallback=f"Analyzed user request and created execution plan. Request is {'modifying' if modifying else 'read-only'}. Risk level: {risk}.",
        )

        plan_record: ExecutionPlanRecord
        if self.context.plan_id:
            plan_record = await self.session.get(ExecutionPlanRecord, self.context.plan_id)
        else:
            plan_record = ExecutionPlanRecord(
                id=str(uuid4()),
                execution_id=self.context.execution_id,
            )
            self.session.add(plan_record)

        plan_record.objective = self.context.user_request[:255]
        plan_record.reasoning = self.context.user_request
        plan_record.repository_ids_json = [self.context.repository_id] if self.context.repository_id else []
        plan_record.affected_files_json = []
        plan_record.required_tools_json = required_tools
        plan_record.execution_order_json = execution_order
        plan_record.risk_score = risk
        plan_record.estimated_duration_ms = sum({
            "ReadFile": 500, "WriteFile": 1000, "CreateFile": 500, "DeleteFile": 500, "MoveFile": 500,
            "SearchRepository": 2000, "ListFiles": 500, "GitStatus": 500, "GitDiff": 1000,
            "CreateBranch": 1000, "CheckoutBranch": 1000, "CommitChanges": 2000, "RollbackCommit": 5000,
            "RunPyTest": 60000, "RunPlaywright": 60000, "RunShellRestricted": 10000, "FormatCode": 5000,
            "QueryVectorStore": 2000, "QueryPostgres": 2000, "ReadLogs": 1000, "RestartContainer": 10000,
        }.get(t, 1000) for t in required_tools)
        plan_record.rollback_strategy = "Capture a checkpoint, restore the saved git SHA and branch, then resync metadata, graph, and vector index."
        plan_record.approval_required = modifying
        plan_record.approval_status = "pending" if modifying else "approved"
        plan_record.execution_id = self.context.execution_id
        plan_record.pipeline_stage = "plan"
        plan_record.ai_reasoning_json = reasoning.model_dump()
        plan_record.plan_json = {
            "objective": self.context.user_request[:255],
            "request_text": self.context.user_request,
            "reasoning": self.context.user_request,
            "repository_ids": [self.context.repository_id] if self.context.repository_id else [],
            "affected_files": [],
            "required_tools": required_tools,
            "execution_order": execution_order,
            "risk_score": risk,
            "approval_required": modifying,
        }
        plan_record.agent_status = "pending"
        await self.session.commit()
        await self.session.refresh(plan_record)

        self.context.plan_id = plan_record.id
        self.context.plan = {
            "plan_id": plan_record.id,
            "objective": self.context.user_request[:255],
            "modifying": modifying,
            "risk": risk,
            "required_tools": required_tools,
            "execution_order": execution_order,
        }

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        await self.append_trace(
            agent_name=self.name,
            ai_reasoning=reasoning,
            input_summary=f"User request: {self.context.user_request[:100]}",
            output_summary=f"Plan created: {plan_id}, risk={risk}, tools={len(required_tools)}",
            tool_calls=0,
            duration_ms=duration_ms,
            success=True,
        )

        await self._save_plan_trace()
        return self.context
