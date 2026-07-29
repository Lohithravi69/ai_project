from __future__ import annotations

import time
from typing import Any


class MetricsCollector:
    def __init__(self) -> None:
        self._start = time.perf_counter()
        self._stage_starts: dict[str, float] = {}
        self._stage_durations: dict[str, float] = {}
        self._planning_time_ms: float = 0.0
        self._tool_execution_time_ms: float = 0.0
        self._validation_time_ms: float = 0.0
        self._rollback_time_ms: float = 0.0

    def start_stage(self, stage_name: str) -> None:
        self._stage_starts[stage_name] = time.perf_counter()

    def end_stage(self, stage_name: str) -> float:
        duration = (time.perf_counter() - self._stage_starts.get(stage_name, self._start)) * 1000
        self._stage_durations[stage_name] = duration
        return duration

    def record_planning(self, duration_ms: float) -> None:
        self._planning_time_ms = duration_ms

    def record_tool_execution(self, duration_ms: float) -> None:
        self._tool_execution_time_ms = duration_ms

    def record_validation(self, duration_ms: float) -> None:
        self._validation_time_ms = duration_ms

    def record_rollback(self, duration_ms: float) -> None:
        self._rollback_time_ms = duration_ms

    @property
    def total_execution_time_ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000

    def to_dict(self) -> dict[str, Any]:
        return {
            "planning_time_ms": self._planning_time_ms,
            "tool_execution_time_ms": self._tool_execution_time_ms,
            "validation_time_ms": self._validation_time_ms,
            "rollback_time_ms": self._rollback_time_ms,
            "total_execution_time_ms": self.total_execution_time_ms,
            "pipeline_stages_timing": dict(self._stage_durations),
        }
