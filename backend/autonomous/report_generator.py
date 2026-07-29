from __future__ import annotations

import json
import time
from typing import Any


class ReportSection:
    def __init__(
        self,
        title: str,
        content: str,
        section_type: str = "text",
        metrics: dict[str, Any] | None = None,
    ) -> None:
        self.title = title
        self.content = content
        self.section_type = section_type
        self.metrics = metrics or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content,
            "type": self.section_type,
            "metrics": self.metrics,
        }


class EngineeringReport:
    def __init__(
        self,
        title: str,
        report_type: str = "engineering",
        summary: str = "",
        sections: list[ReportSection] | None = None,
        metrics: dict[str, Any] | None = None,
        recommendations: list[str] | None = None,
    ) -> None:
        self.title = title
        self.report_type = report_type
        self.summary = summary
        self.sections = sections or []
        self.metrics = metrics or {}
        self.recommendations = recommendations or []
        self.generated_at = time.time()

    def add_section(self, section: ReportSection) -> None:
        self.sections.append(section)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "report_type": self.report_type,
            "summary": self.summary,
            "sections": [s.to_dict() for s in self.sections],
            "metrics": self.metrics,
            "recommendations": self.recommendations,
            "generated_at": self.generated_at,
        }


class ReportGenerator:
    def __init__(self, ollama_client: Any = None) -> None:
        self._ollama = ollama_client

    def generate_execution_report(
        self,
        objective: str,
        task_progress: list[dict[str, Any]],
        analyses: list[dict[str, Any]],
        repair_attempts: int,
        metrics: dict[str, Any],
    ) -> EngineeringReport:
        sections: list[ReportSection] = []

        sections.append(ReportSection(
            title="Execution Overview",
            content=f"Objective: {objective}\nRepair attempts: {repair_attempts}",
            section_type="overview",
            metrics={"total_steps": len(task_progress), "repair_attempts": repair_attempts},
        ))

        completed = [s for s in task_progress if s.get("status") == "completed"]
        failed = [s for s in task_progress if s.get("status") == "failed"]

        sections.append(ReportSection(
            title="Step Results",
            content=f"Completed: {len(completed)}, Failed: {len(failed)}",
            section_type="summary",
            metrics={"completed": len(completed), "failed": len(failed), "total": len(task_progress)},
        ))

        if analyses:
            categories: dict[str, int] = {}
            for a in analyses:
                cat = a.get("category", "unknown")
                categories[cat] = categories.get(cat, 0) + 1
            sections.append(ReportSection(
                title="Failure Analysis",
                content=json.dumps(analyses, indent=2),
                section_type="analysis",
                metrics={"total_analyses": len(analyses), "categories": categories},
            ))

        recommendations: list[str] = []
        for a in analyses:
            strategies = a.get("recovery_strategies", [])
            for s in strategies:
                if s.get("strategy"):
                    recommendations.append(s["strategy"])

        total_duration = metrics.get("total_duration_ms", 0)
        sections.append(ReportSection(
            title="Performance",
            content=f"Total duration: {total_duration}ms",
            section_type="metrics",
            metrics={"total_duration_ms": total_duration, **metrics},
        ))

        return EngineeringReport(
            title=f"Execution Report: {objective[:80]}",
            summary=f"Execution {'completed successfully' if not failed else f'completed with {len(failed)} failures'}",
            sections=sections,
            metrics={**metrics, "total_duration_ms": total_duration},
            recommendations=recommendations,
        )

    async def llm_report(
        self,
        objective: str,
        context: str,
        task_data: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not self._ollama:
            return None
        try:
            import asyncio
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an engineering report writer. Generate a structured report with: "
                        "title (str), summary (str), sections (list of {title, content, type}), "
                        "recommendations (list of str). Return valid JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Objective: {objective}\nContext: {context}\n"
                        f"Data: {json.dumps(task_data, default=str)[:3000]}"
                    ),
                },
            ]
            content = await asyncio.wait_for(self._ollama.chat(messages), timeout=15.0)
            return json.loads(content)
        except Exception:
            return None
