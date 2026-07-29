from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


@dataclass
class ToolSpec:
    id: str = ""
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    permission_level: str = "read"
    timeout_seconds: int = 30
    rollback_support: bool = False
    dry_run_support: bool = True
    input_schema_json: dict[str, Any] = field(default_factory=dict)
    output_schema_json: dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    spec: ToolSpec

    def __init__(self) -> None:
        self.spec = self._build_spec()

    @abstractmethod
    def _build_spec(self) -> ToolSpec:
        ...

    def validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        validated = self._input_model().model_validate(payload)
        return validated.model_dump()

    @abstractmethod
    def _input_model(self) -> type[BaseModel]:
        ...

    @abstractmethod
    async def dry_run(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        ...

    @abstractmethod
    async def execute(self, payload: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        ...

    async def rollback(self, context: dict[str, Any], **kwargs: Any) -> ToolRunResult:
        raise NotImplementedError(f"{self.spec.name} does not support rollback")

    async def cleanup(self, context: dict[str, Any], **kwargs: Any) -> None:
        pass


class ToolRunResult:
    def __init__(
        self,
        success: bool,
        result: dict[str, Any] | None = None,
        affected_files: list[str] | None = None,
        diff_preview: str | None = None,
        estimated_impact: str = "",
        risks: list[str] | None = None,
        exception_message: str = "",
    ) -> None:
        self.success = success
        self.result = result or {}
        self.affected_files = affected_files or []
        self.diff_preview = diff_preview
        self.estimated_impact = estimated_impact
        self.risks = risks or []
        self.exception_message = exception_message
