from __future__ import annotations

import json
import time
from typing import Any
from uuid import uuid4

from backend.autonomous.failure_analyzer import FailureAnalyzer, FailureCategory, FailureAnalysis


class AutonomousTaskEngine:
    def __init__(self, ollama_client: Any = None) -> None:
        self._ollama = ollama_client
        self._failure_analyzer = FailureAnalyzer()
        self._tasks: dict[str, dict[str, Any]] = {}

    def create_task(
        self,
        objective: str,
        mode: str = "full",
        repository_id: str = "",
        max_repair_attempts: int = 3,
    ) -> str:
        task_id = str(uuid4())
        self._tasks[task_id] = {
            "id": task_id,
            "objective": objective,
            "status": "pending",
            "mode": mode,
            "repository_id": repository_id,
            "progress": [],
            "repair_attempts": 0,
            "max_repair_attempts": max_repair_attempts,
            "error_message": "",
            "result_summary": "",
            "metrics": {
                "created_at": time.time(),
                "started_at": None,
                "completed_at": None,
                "total_duration_ms": 0,
            },
            "analyses": [],
        }
        return task_id

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        return self._tasks.get(task_id)

    def update_progress(
        self,
        task_id: str,
        agent_name: str,
        stage: str,
        status: str,
        message: str = "",
        score: float | None = None,
        details: dict | None = None,
    ) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        task["progress"].append({
            "agent_name": agent_name,
            "stage": stage,
            "status": status,
            "message": message,
            "score": score,
            "details": details or {},
        })
        if status == "failed":
            task["status"] = "failed"
        elif status == "completed" and not any(
            p["status"] in ("failed", "running") for p in task["progress"]
        ):
            if all(p["status"] == "completed" for p in task["progress"]):
                task["status"] = "completed"

    def record_failure(
        self,
        task_id: str,
        error_message: str,
        context: str = "",
        details: dict[str, Any] | None = None,
    ) -> FailureAnalysis:
        analysis = self._failure_analyzer.analyze(error_message, context, details)
        task = self._tasks.get(task_id)
        if task:
            task["analyses"].append(analysis.to_dict())
            task["error_message"] = error_message
            if analysis.severity in ("critical", "high"):
                task["status"] = "failed"
        return analysis

    def should_repair(self, task_id: str, analysis: FailureAnalysis | None = None) -> bool:
        task = self._tasks.get(task_id)
        if task is None:
            return False
        if task["repair_attempts"] >= task["max_repair_attempts"]:
            return False
        if analysis and analysis.category in (
            FailureCategory.SECURITY,
            FailureCategory.ARCHITECTURE,
        ):
            return False
        return task["status"] in ("failed", "running")

    def increment_repair(self, task_id: str) -> int:
        task = self._tasks.get(task_id)
        if task is None:
            return 0
        task["repair_attempts"] += 1
        task["status"] = "repairing"
        return task["repair_attempts"]

    def complete_task(
        self,
        task_id: str,
        result_summary: str = "",
        status: str = "completed",
    ) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        task["status"] = status
        task["result_summary"] = result_summary
        task["metrics"]["completed_at"] = time.time()
        if task["metrics"]["started_at"]:
            task["metrics"]["total_duration_ms"] = int(
                (task["metrics"]["completed_at"] - task["metrics"]["started_at"]) * 1000
            )

    def start_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task is None:
            return False
        task["status"] = "running"
        task["metrics"]["started_at"] = time.time()
        return True

    def to_record(self, task_id: str) -> dict[str, Any]:
        task = self._tasks.get(task_id)
        if task is None:
            return {}
        return {
            "id": task["id"],
            "objective": task["objective"],
            "status": task["status"],
            "mode": task["mode"],
            "repository_id": task["repository_id"],
            "result_summary": task["result_summary"],
            "error_message": task["error_message"],
            "repair_attempts": task["repair_attempts"],
            "max_repair_attempts": task["max_repair_attempts"],
            "progress_json": {"steps": task["progress"]},
            "metrics_json": task["metrics"],
        }

    def list_tasks(self, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t["status"] == status]
        tasks.sort(key=lambda t: t["metrics"]["created_at"], reverse=True)
        return tasks[:limit]

    def cancel_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task is None:
            return False
        task["status"] = "cancelled"
        return True

    async def analyze_errors_with_llm(
        self,
        errors: list[str],
        context: str = "",
    ) -> list[dict[str, Any]]:
        if not self._ollama or not errors:
            return [self._failure_analyzer.analyze(e, context).to_dict() for e in errors]
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a failure analysis expert. Categorize each error and suggest recovery steps. "
                        "Return a JSON list of objects with: error (str), category (str), severity (str), "
                        "summary (str), recovery_strategy (str)."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Errors: {json.dumps(errors)}\nContext: {context}",
                },
            ]
            import asyncio
            content = await asyncio.wait_for(self._ollama.chat(messages), timeout=10.0)
            llm_results = json.loads(content)
            results: list[dict[str, Any]] = []
            for item in llm_results if isinstance(llm_results, list) else []:
                analysis = self._failure_analyzer.analyze(
                    item.get("error", ""),
                    context,
                    {"llm_category": item.get("category")},
                )
                results.append(analysis.to_dict())
            return results
        except Exception:
            return [self._failure_analyzer.analyze(e, context).to_dict() for e in errors]
