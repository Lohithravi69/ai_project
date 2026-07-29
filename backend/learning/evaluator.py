from __future__ import annotations

import json
from typing import Any

from backend.models.schemas import ToolRunRequest, ToolRunResponse


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
    ) -> None:
        self.requirements_satisfied = requirements_satisfied
        self.regressions_detected = regressions_detected or []
        self.architecture_consistent = architecture_consistent
        self.refactor_needed = refactor_needed
        self.refactor_suggestions = refactor_suggestions or []
        self.summary = summary
        self.score = score

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirements_satisfied": self.requirements_satisfied,
            "regressions_detected": self.regressions_detected,
            "architecture_consistent": self.architecture_consistent,
            "refactor_needed": self.refactor_needed,
            "refactor_suggestions": self.refactor_suggestions,
            "summary": self.summary,
            "score": self.score,
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
