from __future__ import annotations

from typing import Any


class VersionPlan:
    def __init__(
        self,
        current_version: str,
        suggested_version: str,
        title: str = "",
        summary: str = "",
        reasons: list[str] | None = None,
        changes: list[dict[str, Any]] | None = None,
        risks: list[str] | None = None,
        estimated_effort: str = "medium",
    ) -> None:
        self.current_version = current_version
        self.suggested_version = suggested_version
        self.title = title
        self.summary = summary
        self.reasons = reasons or []
        self.changes = changes or []
        self.risks = risks or []
        self.estimated_effort = estimated_effort

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_version": self.current_version,
            "suggested_version": self.suggested_version,
            "title": self.title,
            "summary": self.summary,
            "reasons": self.reasons,
            "changes": self.changes,
            "risks": self.risks,
            "estimated_effort": self.estimated_effort,
        }


class VersionEvolutionPlanner:
    def __init__(self, ollama_client: Any = None) -> None:
        self._ollama = ollama_client

    def generate_plan(
        self,
        current_version: str,
        debt_summary: dict[str, Any] | None = None,
        arch_changes: list[dict[str, Any]] | None = None,
        dep_recs: list[dict[str, Any]] | None = None,
        perf_findings: list[dict[str, Any]] | None = None,
        sec_findings: list[dict[str, Any]] | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> VersionPlan:
        reasons: list[str] = []
        changes: list[dict[str, Any]] = []
        risks: list[str] = []

        if debt_summary:
            total = debt_summary.get("total_items", 0)
            if total > 10:
                reasons.append(f"Technical debt reduction ({total} items found)")
                changes.append({
                    "type": "refactor",
                    "description": f"Address {total} technical debt items",
                    "category": "maintainability",
                })

        if arch_changes:
            srp = len([c for c in arch_changes if c.get("change_type") == "srp_violation"])
            layer = len([c for c in arch_changes if c.get("change_type") == "layer_violation"])
            if srp > 0:
                reasons.append(f"Architecture improvement — {srp} SRP violations")
                changes.append({
                    "type": "architecture",
                    "description": f"Refactor {srp} classes violating Single Responsibility",
                    "category": "architecture",
                })
            if layer > 0:
                reasons.append(f"Fix {layer} layer separation violations")
                changes.append({
                    "type": "architecture",
                    "description": f"Resolve {layer} layer dependency violations",
                    "category": "architecture",
                })

        if dep_recs:
            breaking = [d for d in dep_recs if d.get("breaking")]
            safe = [d for d in dep_recs if not d.get("breaking") and d.get("category") == "outdated"]
            if breaking:
                reasons.append(f"Dependency upgrades — {len(breaking)} breaking changes planned")
                changes.append({
                    "type": "dependency",
                    "description": f"Upgrade {len(breaking)} packages with breaking changes",
                    "category": "dependencies",
                })
            if safe:
                changes.append({
                    "type": "dependency",
                    "description": f"Upgrade {len(safe)} packages (safe upgrades)",
                    "category": "dependencies",
                })

        if perf_findings:
            high = len([f for f in perf_findings if f.get("severity") == "high"])
            if high > 0:
                reasons.append(f"Performance optimization — {high} high-severity issues")
                changes.append({
                    "type": "performance",
                    "description": f"Fix {high} high-severity performance issues",
                    "category": "performance",
                })

        if sec_findings:
            critical = len([f for f in sec_findings if f.get("severity") == "critical"])
            high = len([f for f in sec_findings if f.get("severity") == "high"])
            if critical > 0 or high > 0:
                reasons.append(f"Security hardening — {critical} critical, {high} high-severity issues")
                changes.append({
                    "type": "security",
                    "description": f"Fix {critical + high} security issues",
                    "category": "security",
                })

        curr_parts = [int(x) for x in current_version.lstrip("v").split(".")]
        suggested_major = curr_parts[0]
        suggested_minor = curr_parts[1] if len(curr_parts) > 1 else 0
        suggested_patch = curr_parts[2] if len(curr_parts) > 2 else 0

        if any(r for r in reasons if "breaking" in r.lower() or "architecture" in r.lower() or "security" in r.lower()):
            suggested_major += 1
            suggested_minor = 0
            suggested_patch = 0
        elif reasons:
            suggested_minor += 1
            suggested_patch = 0
        else:
            suggested_patch += 1

        suggested = f"v{suggested_major}.{suggested_minor}.{suggested_patch}"

        if not reasons:
            reasons.append("Routine maintenance and dependency updates")

        risks.append("Testing required to verify no regressions")
        if any(d.get("breaking") for d in (dep_recs or [])):
            risks.append("Breaking dependency changes may require code updates")

        effort = "large" if (
            len(changes) > 4
            or any(c.get("category") == "architecture" for c in changes)
            or any(c.get("category") == "security" for c in changes)
        ) else ("medium" if len(changes) > 2 else "small")

        summary_lines = []
        if reasons:
            summary_lines.append("This version addresses:")
            for r in reasons:
                summary_lines.append(f"  - {r}")
        summary = "\n".join(summary_lines) if summary_lines else "Routine maintenance release"

        return VersionPlan(
            current_version=current_version,
            suggested_version=suggested,
            title=f"Evolution Plan: {current_version} → {suggested}",
            summary=summary,
            reasons=reasons,
            changes=changes,
            risks=risks,
            estimated_effort=effort,
        )

    async def llm_plan(self, context: str, data: dict[str, Any]) -> dict[str, Any] | None:
        if not self._ollama:
            return None
        try:
            import asyncio
            import json
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a version evolution planner. Given the current state of a codebase, "
                        "generate a version upgrade plan with: current_version, suggested_version, "
                        "title, summary, reasons (list), changes (list of {type, description, category}), "
                        "risks (list), estimated_effort (small/medium/large). Return valid JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Context: {context}\nData: {json.dumps(data, default=str)[:4000]}",
                },
            ]
            content = await asyncio.wait_for(self._ollama.chat(messages), timeout=15.0)
            return json.loads(content)
        except Exception:
            return None
