from __future__ import annotations

from typing import Any

from backend.config import get_settings

MAX_EXECUTION_TIMEOUT = 600
MAX_FILE_SIZE_BYTES = 10_000_000
MAX_CHANGED_FILES = 100
MAX_EXECUTION_DEPTH = 5


class PermissionValidator:
    def __init__(self) -> None:
        self.settings = get_settings()

    def validate_tool_permission(self, tool_name: str, permission_level: str, user_role: str = "developer") -> None:
        if permission_level == "admin" and user_role != "admin":
            raise PermissionError(f"Tool {tool_name} requires admin privileges")

    def validate_file_size(self, size_bytes: int) -> None:
        if size_bytes > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"File size {size_bytes} exceeds maximum {MAX_FILE_SIZE_BYTES}")

    def validate_changed_files(self, count: int) -> None:
        if count > MAX_CHANGED_FILES:
            raise ValueError(f"Changed file count {count} exceeds maximum {MAX_CHANGED_FILES}")

    def validate_timeout(self, timeout_seconds: int) -> None:
        if timeout_seconds > MAX_EXECUTION_TIMEOUT:
            raise ValueError(f"Timeout {timeout_seconds}s exceeds maximum {MAX_EXECUTION_TIMEOUT}s")

    def validate_execution_depth(self, current_depth: int) -> None:
        if current_depth >= MAX_EXECUTION_DEPTH:
            raise ValueError(f"Execution depth {current_depth} exceeds maximum {MAX_EXECUTION_DEPTH}")

    def validate_workspace_path(self, workspace_path: str, repositories_root: str) -> None:
        import os

        real_workspace = os.path.realpath(workspace_path)
        real_repos_root = os.path.realpath(repositories_root)
        if not real_workspace.startswith(real_repos_root):
            raise PermissionError(f"Workspace path {workspace_path} is outside allowed root {repositories_root}")

    def validate_sql_read_only(self, sql: str) -> None:
        import re

        stripped = sql.strip()
        if not re.match(r"^(select|with)\b", stripped, flags=re.IGNORECASE):
            raise ValueError("Only read-only SELECT/WITH statements are allowed")

    def validate_allowed_command(self, command: str, allow_list: list[str]) -> None:
        import os
        import shlex

        normalized = " ".join(shlex.split(command, posix=os.name != "nt")).lower()
        if not any(normalized.startswith(prefix) for prefix in allow_list):
            raise ValueError(f"Command is not in the allowed list: {command}")

    def validate_request(self, checks: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for key, (validator, value) in checks.items():
            try:
                validator(value)
            except (ValueError, PermissionError) as exc:
                errors.append(f"{key}: {exc}")
        return errors
