from __future__ import annotations

from typing import Any


class AgentOrchestrator:
    """Construct prompts for repository-aware assistant behavior."""

    @staticmethod
    def build_system_prompt(repository_name: str, context_snippets: list[dict[str, Any]]) -> str:
        snippet_lines = []
        for item in context_snippets:
            source = item.get("metadata", {}).get("path", "unknown")
            snippet_lines.append(f"Source: {source}\n{item.get('content', '')}")
        context_text = "\n\n".join(snippet_lines)
        return (
            "You are a local codebase assistant for a developer workspace. "
            f"Repository: {repository_name}. "
            "Use only the provided repository context and call out uncertainty clearly.\n\n"
            f"Context:\n{context_text}"
        )
