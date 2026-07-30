from __future__ import annotations

import time
from typing import Any
from uuid import uuid4


class PrioritizedRecommendation:
    def __init__(
        self,
        category: str,
        title: str,
        description: str,
        severity: str = "medium",
        priority: str = "medium",
        rationale: str = "",
        effort_estimate: str = "medium",
        source: str = "",
        affected_files: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.id = str(uuid4())
        self.category = category
        self.title = title
        self.description = description
        self.severity = severity
        self.priority = priority
        self.rationale = rationale
        self.effort_estimate = effort_estimate
        self.source = source
        self.affected_files = affected_files or []
        self.metadata = metadata or {}
        self.status = "open"
        self.created_at = time.time()
        self.approved_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "priority": self.priority,
            "rationale": self.rationale,
            "effort_estimate": self.effort_estimate,
            "source": self.source,
            "affected_files": self.affected_files,
            "metadata": self.metadata,
            "status": self.status,
            "created_at": self.created_at,
            "approved_at": self.approved_at,
        }


_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_EFFORT_ORDER = {"small": 0, "medium": 1, "large": 2}


class RecommendationCenter:
    def __init__(self) -> None:
        self._recommendations: list[PrioritizedRecommendation] = []

    def add(self, rec: PrioritizedRecommendation) -> str:
        self._recommendations.append(rec)
        return rec.id

    def add_from_debt(self, items: list[dict[str, Any]]) -> list[str]:
        ids: list[str] = []
        for item in items:
            rec = PrioritizedRecommendation(
                category="technical_debt",
                title=item.get("description", "Technical debt item")[:255],
                description=item.get("description", ""),
                severity=item.get("severity", "medium"),
                priority=self._map_priority(item.get("severity", "medium")),
                rationale=f"Technical debt: {item.get('category', 'unknown')} in {item.get('file_path', '')}",
                effort_estimate=self._estimate_effort(item),
                source="debt_analyzer",
                affected_files=[item.get("file_path", "")] if item.get("file_path") else [],
                metadata=item,
            )
            ids.append(self.add(rec))
        return ids

    def add_from_security(self, findings: list[dict[str, Any]]) -> list[str]:
        ids: list[str] = []
        for finding in findings:
            rec = PrioritizedRecommendation(
                category="security",
                title=finding.get("description", "Security finding")[:255],
                description=finding.get("description", ""),
                severity=finding.get("severity", "high"),
                priority=self._map_priority(finding.get("severity", "high")),
                rationale=f"Security: {finding.get('finding_type', 'unknown')} at line {finding.get('line_number', 0)}",
                effort_estimate="medium",
                source="security_advisor",
                affected_files=[finding.get("file_path", "")] if finding.get("file_path") else [],
                metadata=finding,
            )
            ids.append(self.add(rec))
        return ids

    def add_from_perf(self, findings: list[dict[str, Any]]) -> list[str]:
        ids: list[str] = []
        for finding in findings:
            rec = PrioritizedRecommendation(
                category="performance",
                title=finding.get("description", "Performance finding")[:255],
                description=finding.get("description", ""),
                severity=finding.get("severity", "medium"),
                priority=self._map_priority(finding.get("severity", "medium")),
                rationale=f"Performance: {finding.get('finding_type', 'unknown')} in {finding.get('file_path', '')}",
                effort_estimate="small",
                source="performance_advisor",
                affected_files=[finding.get("file_path", "")] if finding.get("file_path") else [],
                metadata=finding,
            )
            ids.append(self.add(rec))
        return ids

    def add_from_deps(self, recs: list[dict[str, Any]]) -> list[str]:
        ids: list[str] = []
        for r in recs:
            rec = PrioritizedRecommendation(
                category="dependencies",
                title=f"Upgrade {r.get('package', 'unknown')}: {r.get('current_version', '?')} → {r.get('suggested_version', '?')}",
                description=r.get("description", ""),
                severity=r.get("severity", "medium"),
                priority=self._map_priority(r.get("severity", "medium")),
                rationale=f"Dependency: {r.get('package', '')} is outdated",
                effort_estimate="small" if not r.get("breaking") else "medium",
                source="dependency_intel",
                metadata=r,
            )
            ids.append(self.add(rec))
        return ids

    def add_from_arch(self, changes: list[dict[str, Any]]) -> list[str]:
        ids: list[str] = []
        for change in changes:
            rec = PrioritizedRecommendation(
                category="architecture",
                title=change.get("description", "Architecture improvement")[:255],
                description=change.get("description", ""),
                severity=change.get("severity", "medium"),
                priority=self._map_priority(change.get("severity", "medium")),
                rationale=f"Architecture: {change.get('principle', '')} violation",
                effort_estimate="large",
                source="architecture_engine",
                affected_files=change.get("affected_files", []),
                metadata=change,
            )
            ids.append(self.add(rec))
        return ids

    def _map_priority(self, severity: str) -> str:
        return {"critical": "high", "high": "high", "medium": "medium", "low": "low"}.get(severity, "medium")

    def _estimate_effort(self, item: dict[str, Any]) -> str:
        cat = item.get("category", "")
        if cat in ("god_class", "architecture"):
            return "large"
        if cat in ("long_method", "high_complexity"):
            return "medium"
        return "small"

    def get_all(self, status: str | None = None, limit: int = 100) -> list[PrioritizedRecommendation]:
        recs = self._recommendations
        if status:
            recs = [r for r in recs if r.status == status]
        recs.sort(key=lambda r: (_SEVERITY_ORDER.get(r.severity, 99), _EFFORT_ORDER.get(r.effort_estimate, 99)))
        return recs[:limit]

    def get_grouped(self) -> dict[str, list[dict[str, Any]]]:
        groups: dict[str, list[PrioritizedRecommendation]] = {}
        for rec in self._recommendations:
            groups.setdefault(rec.category, []).append(rec)

        result: dict[str, list[dict[str, Any]]] = {}
        for cat, recs in groups.items():
            result[cat] = [r.to_dict() for r in recs[:20]]
        return result

    def get_by_priority(self) -> dict[str, list[dict[str, Any]]]:
        priority_groups: dict[str, list[PrioritizedRecommendation]] = {
            "high": [], "medium": [], "low": [],
        }
        for rec in self._recommendations:
            if rec.status != "open":
                continue
            priority_groups.setdefault(rec.priority, []).append(rec)

        result: dict[str, list[dict[str, Any]]] = {}
        for priority, recs in priority_groups.items():
            recs.sort(key=lambda r: _SEVERITY_ORDER.get(r.severity, 99))
            result[priority] = [r.to_dict() for r in recs[:15]]
        return result

    def approve(self, rec_id: str) -> bool:
        for rec in self._recommendations:
            if rec.id == rec_id:
                rec.status = "approved"
                rec.approved_at = time.time()
                return True
        return False

    def dismiss(self, rec_id: str) -> bool:
        for rec in self._recommendations:
            if rec.id == rec_id:
                rec.status = "dismissed"
                return True
        return False

    def get_stats(self) -> dict[str, Any]:
        total = len(self._recommendations)
        open_recs = len([r for r in self._recommendations if r.status == "open"])
        approved = len([r for r in self._recommendations if r.status == "approved"])
        dismissed = len([r for r in self._recommendations if r.status == "dismissed"])

        return {
            "total": total,
            "open": open_recs,
            "approved": approved,
            "dismissed": dismissed,
            "by_category": {
                cat: len([r for r in self._recommendations if r.category == cat])
                for cat in set(r.category for r in self._recommendations)
            },
            "by_priority": {
                p: len([r for r in self._recommendations if r.priority == p])
                for p in ["high", "medium", "low"]
            },
        }
