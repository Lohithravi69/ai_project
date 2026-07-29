from __future__ import annotations

from typing import Any

from backend.learning.experience_store import ExperienceEntry, ExperienceStore


class RepoAnalytics:
    def __init__(self, experience_store: ExperienceStore | None = None) -> None:
        self._store = experience_store or ExperienceStore()

    def defect_rate(self, repository_id: str = "") -> float:
        entries = self._store.list_recent(limit=1000)
        if repository_id:
            entries = [e for e in entries if e.repository_id == repository_id]
        if not entries:
            return 0.0
        failed = sum(1 for e in entries if e.outcome == "failure" or e.failures)
        return failed / len(entries)

    def frequently_changed_files(self, repository_id: str = "", top_n: int = 10) -> list[dict[str, Any]]:
        entries = self._store.list_recent(limit=1000)
        if repository_id:
            entries = [e for e in entries if e.repository_id == repository_id]
        file_counts: dict[str, int] = {}
        for entry in entries:
            for tool in entry.tools_used:
                if tool in ("WriteFile", "CreateFile", "DeleteFile", "MoveFile"):
                    file_counts[tool] = file_counts.get(tool, 0) + 1
        sorted_files = sorted(file_counts.items(), key=lambda x: -x[1])
        return [
            {"file": fname, "change_count": count}
            for fname, count in sorted_files[:top_n]
        ]

    def common_failure_patterns(self, repository_id: str = "", top_n: int = 5) -> list[dict[str, Any]]:
        entries = self._store.list_recent(limit=1000)
        if repository_id:
            entries = [e for e in entries if e.repository_id == repository_id]
        failure_reasons: dict[str, int] = {}
        for entry in entries:
            for failure in entry.failures:
                key = failure[:100]
                failure_reasons[key] = failure_reasons.get(key, 0) + 1
        sorted_reasons = sorted(failure_reasons.items(), key=lambda x: -x[1])
        return [
            {"failure": reason, "count": count}
            for reason, count in sorted_reasons[:top_n]
        ]

    def avg_duration_by_outcome(self, repository_id: str = "") -> dict[str, float]:
        entries = self._store.list_recent(limit=1000)
        if repository_id:
            entries = [e for e in entries if e.repository_id == repository_id]
        groups: dict[str, list[int]] = {}
        for entry in entries:
            outcome = entry.outcome or "unknown"
            if outcome not in groups:
                groups[outcome] = []
            groups[outcome].append(entry.duration_ms)
        return {
            outcome: sum(durations) / max(len(durations), 1)
            for outcome, durations in groups.items()
        }

    def tool_usage_frequency(self, repository_id: str = "", top_n: int = 10) -> list[dict[str, Any]]:
        entries = self._store.list_recent(limit=1000)
        if repository_id:
            entries = [e for e in entries if e.repository_id == repository_id]
        tool_counts: dict[str, int] = {}
        for entry in entries:
            for tool in entry.tools_used:
                tool_counts[tool] = tool_counts.get(tool, 0) + 1
        sorted_tools = sorted(tool_counts.items(), key=lambda x: -x[1])
        return [
            {"tool": tool, "count": count}
            for tool, count in sorted_tools[:top_n]
        ]

    def summary(self, repository_id: str = "") -> dict[str, Any]:
        entries = self._store.list_recent(limit=1000)
        if repository_id:
            entries = [e for e in entries if e.repository_id == repository_id]
        if not entries:
            return {"error": "No data available"}
        total = len(entries)
        successes = sum(1 for e in entries if e.outcome == "success" and not e.failures)
        failures = total - successes
        return {
            "total_executions": total,
            "success_rate": round(successes / max(total, 1), 3),
            "failure_rate": round(failures / max(total, 1), 3),
            "avg_duration_ms": round(sum(e.duration_ms for e in entries) / max(total, 1), 1),
            "most_used_tools": self.tool_usage_frequency(repository_id, 5),
            "common_failures": self.common_failure_patterns(repository_id, 3),
        }
