from __future__ import annotations

import json
from typing import Any

from backend.models.schemas import ToolRunRequest, ToolRunResponse


class AgentScore:
    def __init__(
        self,
        agent_name: str = "",
        correctness: float = 1.0,
        completeness: float = 1.0,
        code_quality: float = 1.0,
        architecture: float = 1.0,
        performance: float = 1.0,
        security: float = 1.0,
        testing: float = 1.0,
        overall: float = 1.0,
        details: list[str] | None = None,
    ) -> None:
        self.agent_name = agent_name
        self.correctness = correctness
        self.completeness = completeness
        self.code_quality = code_quality
        self.architecture = architecture
        self.performance = performance
        self.security = security
        self.testing = testing
        self.overall = overall
        self.details = details or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "correctness": self.correctness,
            "completeness": self.completeness,
            "code_quality": self.code_quality,
            "architecture": self.architecture,
            "performance": self.performance,
            "security": self.security,
            "testing": self.testing,
            "overall": self.overall,
            "details": self.details,
        }


class EvaluationResult:
    def __init__(
        self,
        requirements_satisfied: bool = True,
        regressions_detected: list[str] | None = None,
        architecture_consistent: bool = True,
        refactor_needed: bool = False,
        refactor_suggestions: list[str] | None = None,
        summary: str = "",
        score: float = 1.0,
        agent_scores: list[AgentScore] | None = None,
    ) -> None:
        self.requirements_satisfied = requirements_satisfied
        self.regressions_detected = regressions_detected or []
        self.architecture_consistent = architecture_consistent
        self.refactor_needed = refactor_needed
        self.refactor_suggestions = refactor_suggestions or []
        self.summary = summary
        self.score = score
        self.agent_scores = agent_scores or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirements_satisfied": self.requirements_satisfied,
            "regressions_detected": self.regressions_detected,
            "architecture_consistent": self.architecture_consistent,
            "refactor_needed": self.refactor_needed,
            "refactor_suggestions": self.refactor_suggestions,
            "summary": self.summary,
            "score": self.score,
            "agent_scores": [s.to_dict() for s in self.agent_scores],
        }

    @property
    def passed(self) -> bool:
        return (
            self.requirements_satisfied
            and not self.regressions_detected
            and self.architecture_consistent
            and not self.refactor_needed
        )


class SelfEvaluator:
    def __init__(self, ollama_client: Any = None) -> None:
        self._ollama = ollama_client

    async def evaluate(
        self,
        user_request: str,
        tool_requests: list[ToolRunRequest],
        tool_responses: list[ToolRunResponse],
        errors: list[str],
    ) -> EvaluationResult:
        regressions: list[str] = []
        refactor_suggestions: list[str] = []
        summary_parts: list[str] = []

        if errors:
            summary_parts.append(f"{len(errors)} error(s) occurred")
            for err in errors:
                if "test" in err.lower() or "assert" in err.lower():
                    regressions.append(f"Test failure: {err}")

        for resp in tool_responses:
            if not resp.success:
                regressions.append(f"{resp.tool_name} failed: {resp.exception_message}")

        if self._ollama:
            llm_eval = await self._llm_evaluate(user_request, tool_requests, tool_responses, errors)
            regressions.extend(llm_eval.get("regressions", []))
            refactor_suggestions.extend(llm_eval.get("refactor_suggestions", []))
            if llm_eval.get("summary"):
                summary_parts.append(llm_eval["summary"])
            llm_req_satisfied = llm_eval.get("requirements_satisfied", True)
            llm_arch_consistent = llm_eval.get("architecture_consistent", True)
        else:
            llm_req_satisfied = True
            llm_arch_consistent = True

        if not summary_parts:
            if not regressions and not errors:
                summary_parts.append("All checks passed")
            else:
                summary_parts.append("Issues detected")

        non_test_errors = [e for e in errors if "test" not in e.lower() and "assert" not in e.lower()]

        score = 1.0
        if regressions:
            score -= 0.2 * len(regressions)
        if non_test_errors:
            score -= 0.15 * len(non_test_errors)
        if not llm_req_satisfied:
            score -= 0.3
        if not llm_arch_consistent:
            score -= 0.2
        if refactor_suggestions:
            score -= 0.1
        score = max(0.0, min(1.0, score))

        return EvaluationResult(
            requirements_satisfied=llm_req_satisfied and not non_test_errors,
            regressions_detected=regressions,
            architecture_consistent=llm_arch_consistent,
            refactor_needed=bool(refactor_suggestions),
            refactor_suggestions=refactor_suggestions,
            summary="; ".join(summary_parts),
            score=score,
        )

    def evaluate_agent(
        self,
        agent_name: str,
        success: bool,
        error_count: int = 0,
        tool_call_count: int = 0,
        duration_ms: int = 0,
        complexity: float = 0.5,
    ) -> AgentScore:
        base = 1.0
        details: list[str] = []

        if not success:
            base -= 0.4
            details.append("Agent failed execution")
        if error_count > 0:
            base -= 0.15 * min(error_count, 5)
            details.append(f"{error_count} error(s) encountered")
        if tool_call_count == 0 and success:
            base -= 0.1
            details.append("No tool calls made")

        correctness = max(0.0, base - 0.1 * (error_count > 0))
        completeness = max(0.0, base - 0.1 * (0 if success else 1))
        code_quality = max(0.0, base - 0.05 * complexity)
        architecture = max(0.0, base - 0.1 * complexity)
        performance = max(0.0, 1.0 - min(duration_ms / 60000, 0.5))
        security = max(0.0, base - 0.3 * (1 if agent_name == "reviewer" and error_count > 0 else 0))
        testing = max(0.0, base + 0.1 * (0 if agent_name == "tester" and not success else 0))

        overall = (
            correctness * 0.25 + completeness * 0.2 + code_quality * 0.15
            + architecture * 0.1 + performance * 0.1 + security * 0.1 + testing * 0.1
        )

        return AgentScore(
            agent_name=agent_name,
            correctness=round(correctness, 2),
            completeness=round(completeness, 2),
            code_quality=round(code_quality, 2),
            architecture=round(architecture, 2),
            performance=round(performance, 2),
            security=round(security, 2),
            testing=round(testing, 2),
            overall=round(overall, 2),
            details=details,
        )

    async def _llm_evaluate(
        self,
        user_request: str,
        tool_requests: list[ToolRunRequest],
        tool_responses: list[ToolRunResponse],
        errors: list[str],
    ) -> dict[str, Any]:
        if not self._ollama:
            return {}
        try:
            import asyncio

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a code review evaluator. Assess whether the implementation "
                        "satisfies requirements, introduces regressions, is architecturally "
                        "consistent, and needs refactoring. Return JSON with: "
                        "requirements_satisfied (bool), regressions (list of str), "
                        "architecture_consistent (bool), refactor_suggestions (list of str), "
                        "summary (str)."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Request: {user_request}\n"
                        f"Tool calls: {len(tool_requests)}\n"
                        f"Tool responses: {len(tool_responses)}\n"
                        f"Errors: {errors}"
                    ),
                },
            ]
            content = await asyncio.wait_for(self._ollama.chat(messages), timeout=8.0)
            data = json.loads(content)
            return {
                "requirements_satisfied": bool(data.get("requirements_satisfied", True)),
                "regressions": data.get("regressions", []),
                "architecture_consistent": bool(data.get("architecture_consistent", True)),
                "refactor_suggestions": data.get("refactor_suggestions", []),
                "summary": data.get("summary", ""),
            }
        except Exception:
            return {}
