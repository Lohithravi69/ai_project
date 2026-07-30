from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

EXPERIENCES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "experiences")


class ExperienceEntry:
    def __init__(
        self,
        objective: str = "",
        plan_summary: str = "",
        tools_used: list[str] | None = None,
        failures: list[str] | None = None,
        fixes: list[str] | None = None,
        duration_ms: int = 0,
        outcome: str = "",
        pattern_refs: list[str] | None = None,
        execution_id: str = "",
        repository_id: str = "",
    ) -> None:
        self.id: str = str(uuid4())
        self.execution_id: str = execution_id
        self.repository_id: str = repository_id
        self.objective: str = objective
        self.plan_summary: str = plan_summary
        self.tools_used: list[str] = tools_used or []
        self.failures: list[str] = failures or []
        self.fixes: list[str] = fixes or []
        self.duration_ms: int = duration_ms
        self.outcome: str = outcome
        self.pattern_refs: list[str] = pattern_refs or []
        self.created_at: str = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "repository_id": self.repository_id,
            "objective": self.objective,
            "plan_summary": self.plan_summary,
            "tools_used": self.tools_used,
            "failures": self.failures,
            "fixes": self.fixes,
            "duration_ms": self.duration_ms,
            "outcome": self.outcome,
            "pattern_refs": self.pattern_refs,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperienceEntry:
        entry = cls()
        entry.id = data.get("id", entry.id)
        entry.execution_id = data.get("execution_id", "")
        entry.repository_id = data.get("repository_id", "")
        entry.objective = data.get("objective", "")
        entry.plan_summary = data.get("plan_summary", "")
        entry.tools_used = data.get("tools_used", [])
        entry.failures = data.get("failures", [])
        entry.fixes = data.get("fixes", [])
        entry.duration_ms = data.get("duration_ms", 0)
        entry.outcome = data.get("outcome", "")
        entry.pattern_refs = data.get("pattern_refs", [])
        entry.created_at = data.get("created_at", entry.created_at)
        return entry


class ExperienceStore:
    def __init__(self, directory: str = EXPERIENCES_DIR) -> None:
        self._directory = directory
        os.makedirs(directory, exist_ok=True)
        self._index_path = os.path.join(directory, "index.json")
        self._index: dict[str, dict[str, Any]] = {}
        self._load_index()

    def _load_index(self) -> None:
        if os.path.isfile(self._index_path):
            try:
                with open(self._index_path, encoding="utf-8") as f:
                    self._index = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._index = {}

    def _save_index(self) -> None:
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2, default=str)

    def store(self, entry: ExperienceEntry) -> None:
        file_path = os.path.join(self._directory, f"{entry.id}.json")
        data = entry.to_dict()
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        self._index[entry.id] = {
            "objective": entry.objective[:200],
            "outcome": entry.outcome,
            "tools_used": entry.tools_used,
            "failures_count": len(entry.failures),
            "duration_ms": entry.duration_ms,
            "created_at": entry.created_at,
            "repository_id": entry.repository_id,
        }
        self._save_index()

    def auto_record(
        self,
        objective: str,
        outcome: str = "success",
        plan_summary: str = "",
        tools_used: list[str] | None = None,
        failures: list[str] | None = None,
        fixes: list[str] | None = None,
        duration_ms: int = 0,
        execution_id: str = "",
        repository_id: str = "",
    ) -> ExperienceEntry:
        entry = ExperienceEntry(
            objective=objective,
            plan_summary=plan_summary,
            tools_used=tools_used,
            failures=failures,
            fixes=fixes,
            duration_ms=duration_ms,
            outcome=outcome,
            execution_id=execution_id,
            repository_id=repository_id,
        )
        self.store(entry)
        return entry

    def get(self, entry_id: str) -> ExperienceEntry | None:
        if entry_id not in self._index:
            return None
        file_path = os.path.join(self._directory, f"{entry_id}.json")
        if not os.path.isfile(file_path):
            return None
        try:
            with open(file_path, encoding="utf-8") as f:
                return ExperienceEntry.from_dict(json.load(f))
        except (json.JSONDecodeError, OSError):
            return None

    def search(self, q: str, limit: int = 5) -> list[tuple[ExperienceEntry, float]]:
        return self.search_similar(q, limit)

    def list_all(self, limit: int = 50, offset: int = 0) -> list[ExperienceEntry]:
        sorted_ids = sorted(
            self._index.keys(),
            key=lambda eid: self._index[eid].get("created_at", ""),
            reverse=True,
        )
        entries: list[ExperienceEntry] = []
        for eid in sorted_ids[offset:offset + limit]:
            entry = self.get(eid)
            if entry:
                entries.append(entry)
        return entries

    def search_similar(self, query: str, limit: int = 5) -> list[tuple[ExperienceEntry, float]]:
        query_lower = query.lower()
        query_words = set(query_lower.split())
        scored: list[tuple[str, float]] = []

        for eid, meta in self._index.items():
            obj_lower = meta.get("objective", "").lower()
            word_overlap = len(query_words & set(obj_lower.split()))
            if word_overlap > 0:
                scored.append((eid, word_overlap / max(len(query_words), 1)))

        scored.sort(key=lambda x: -x[1])
        results: list[tuple[ExperienceEntry, float]] = []
        for eid, score in scored[:limit]:
            entry = self.get(eid)
            if entry:
                results.append((entry, score))
        return results

    def list_recent(self, limit: int = 20) -> list[ExperienceEntry]:
        sorted_ids = sorted(
            self._index.keys(),
            key=lambda eid: self._index[eid].get("created_at", ""),
            reverse=True,
        )
        entries: list[ExperienceEntry] = []
        for eid in sorted_ids[:limit]:
            entry = self.get(eid)
            if entry:
                entries.append(entry)
        return entries

    def count(self) -> int:
        return len(self._index)

    def clear(self) -> None:
        self._index = {}
        for fname in os.listdir(self._directory):
            if fname.endswith(".json"):
                try:
                    os.remove(os.path.join(self._directory, fname))
                except OSError:
                    pass
        self._save_index()
