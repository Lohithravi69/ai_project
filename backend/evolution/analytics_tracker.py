from __future__ import annotations

import time
from typing import Any


class TrendSnapshot:
    def __init__(
        self,
        metric_name: str,
        metric_value: float,
        metric_unit: str = "",
        direction: str = "stable",
        change_percent: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.metric_name = metric_name
        self.metric_value = metric_value
        self.metric_unit = metric_unit
        self.direction = direction
        self.change_percent = change_percent
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "metric_unit": self.metric_unit,
            "direction": self.direction,
            "change_percent": self.change_percent,
            "metadata": self.metadata,
        }


class AnalyticsTracker:
    def __init__(self) -> None:
        self._history: dict[str, list[dict[str, Any]]] = {}

    def record(self, metric_name: str, value: float, unit: str = "", metadata: dict[str, Any] | None = None) -> TrendSnapshot:
        now = time.time()
        previous = self._get_previous(metric_name)
        change_percent = 0.0
        direction = "stable"

        if previous is not None and previous != 0:
            change_percent = round((value - previous) / previous * 100, 1)
            direction = "up" if change_percent > 5 else ("down" if change_percent < -5 else "stable")

        entry = {
            "timestamp": now,
            "value": value,
            "unit": unit,
            "direction": direction,
            "change_percent": change_percent,
        }
        self._history.setdefault(metric_name, []).append(entry)

        return TrendSnapshot(
            metric_name=metric_name,
            metric_value=value,
            metric_unit=unit,
            direction=direction,
            change_percent=change_percent,
            metadata=metadata,
        )

    def _get_previous(self, metric_name: str) -> float | None:
        entries = self._history.get(metric_name, [])
        if not entries:
            return None
        return entries[-1]["value"]

    def get_trend(self, metric_name: str, limit: int = 10) -> list[dict[str, Any]]:
        return self._history.get(metric_name, [])[-limit:]

    def get_summary(self) -> dict[str, Any]:
        improving = 0
        declining = 0
        stable = 0
        metrics: list[dict[str, Any]] = []

        for name, entries in self._history.items():
            if not entries:
                continue
            latest = entries[-1]
            direction = latest["direction"]
            if direction == "up":
                improving += 1
            elif direction == "down":
                declining += 1
            else:
                stable += 1

            metrics.append({
                "name": name,
                "current_value": latest["value"],
                "unit": latest.get("unit", ""),
                "direction": direction,
                "change_percent": latest.get("change_percent", 0),
                "data_points": len(entries),
            })

        return {
            "total_metrics": len(metrics),
            "improving": improving,
            "declining": declining,
            "stable": stable,
            "health_score": self._calculate_health_score(metrics),
            "metrics": metrics,
        }

    def _calculate_health_score(self, metrics: list[dict[str, Any]]) -> float:
        if not metrics:
            return 1.0

        score = 1.0
        for m in metrics:
            direction = m.get("direction", "stable")
            if direction == "up":
                score += 0.05
            elif direction == "down":
                score -= 0.1
            change = abs(m.get("change_percent", 0))
            if change > 50:
                score -= 0.1

        return max(0.0, min(1.0, score))

    def compute_debt_score(self, debt_items: list[dict[str, Any]]) -> float:
        if not debt_items:
            return 0.0
        severity_weight = {"critical": 10, "high": 5, "medium": 2, "low": 0.5}
        total = sum(severity_weight.get(i.get("severity", "low"), 0.5) for i in debt_items)
        return min(100, total)

    def compute_coverage_trend(self, current: float, previous: float | None = None) -> TrendSnapshot:
        change = round(current - (previous or current), 1)
        direction = "up" if change > 1 else ("down" if change < -1 else "stable")
        return TrendSnapshot(
            metric_name="test_coverage",
            metric_value=current,
            metric_unit="%",
            direction=direction,
            change_percent=round(change / (previous or current) * 100 if (previous or current) > 0 else 0, 1),
        )

    def compute_churn(self, files_changed: int, total_files: int) -> TrendSnapshot:
        ratio = round(files_changed / max(total_files, 1) * 100, 1)
        return TrendSnapshot(
            metric_name="code_churn",
            metric_value=ratio,
            metric_unit="%",
            direction="stable",
            change_percent=0.0,
            metadata={"files_changed": files_changed, "total_files": total_files},
        )
