from __future__ import annotations

from typing import Any

from backend.tool_registry.base import BaseTool, ToolSpec
from backend.tool_registry.tools import ALL_TOOLS


class ToolRegistry:
    _instance: ToolRegistry | None = None
    _tools: dict[str, BaseTool] = {}

    def __new__(cls) -> ToolRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
            cls._instance._register_all()
        return cls._instance

    def _register_all(self) -> None:
        for tool_cls in ALL_TOOLS:
            tool = tool_cls()
            self._tools[tool.spec.name] = tool

    def get_tool(self, name: str) -> BaseTool:
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")
        return tool

    def list_tools(self) -> list[ToolSpec]:
        return [tool.spec for tool in self._tools.values()]

    def list_tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def get_spec(self, name: str) -> ToolSpec:
        return self.get_tool(name).spec

    def validate_input(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.get_tool(name).validate(payload)

    async def dry_run(self, name: str, payload: dict[str, Any], **kwargs: Any) -> Any:
        return await self.get_tool(name).dry_run(self.validate_input(name, payload), **kwargs)

    async def execute(self, name: str, payload: dict[str, Any], **kwargs: Any) -> Any:
        return await self.get_tool(name).execute(self.validate_input(name, payload), **kwargs)

    async def rollback(self, name: str, context: dict[str, Any], **kwargs: Any) -> Any:
        return await self.get_tool(name).rollback(context, **kwargs)

    async def cleanup(self, name: str, context: dict[str, Any], **kwargs: Any) -> None:
        await self.get_tool(name).cleanup(context, **kwargs)
