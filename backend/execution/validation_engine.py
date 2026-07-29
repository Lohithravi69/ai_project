from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from backend.config import get_settings


class ValidationResult:
    def __init__(
        self,
        success: bool,
        validator: str = "",
        output: str = "",
        errors: list[str] | None = None,
        duration_ms: int = 0,
    ) -> None:
        self.success = success
        self.validator = validator
        self.output = output
        self.errors = errors or []
        self.duration_ms = duration_ms


class ValidationEngine:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def run_tests(self, repo_path: str, test_path: str | None = None) -> ValidationResult:
        import time

        start = time.perf_counter()
        cmd = ["python", "-m", "pytest"]
        if test_path:
            cmd.append(test_path)
        try:
            completed = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True, timeout=300)
            duration_ms = int((time.perf_counter() - start) * 1000)
            return ValidationResult(
                success=completed.returncode == 0,
                validator="pytest",
                output=completed.stdout + "\n" + completed.stderr,
                errors=[] if completed.returncode == 0 else ["Tests failed"],
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return ValidationResult(success=False, validator="pytest", output="", errors=["Test execution timed out"], duration_ms=duration_ms)

    async def run_formatter(self, repo_path: str, tool: str = "ruff") -> ValidationResult:
        import time

        start = time.perf_counter()
        try:
            completed = subprocess.run([tool, "check", "."], cwd=repo_path, capture_output=True, text=True, timeout=60)
            duration_ms = int((time.perf_counter() - start) * 1000)
            return ValidationResult(
                success=completed.returncode == 0,
                validator=tool,
                output=completed.stdout + "\n" + completed.stderr,
                duration_ms=duration_ms,
            )
        except FileNotFoundError:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return ValidationResult(success=True, validator=tool, output=f"{tool} not found, skipping", duration_ms=duration_ms)

    async def run_linter(self, repo_path: str, tool: str = "ruff") -> ValidationResult:
        import time

        start = time.perf_counter()
        try:
            completed = subprocess.run([tool, "check", "."], cwd=repo_path, capture_output=True, text=True, timeout=60)
            duration_ms = int((time.perf_counter() - start) * 1000)
            return ValidationResult(
                success=completed.returncode == 0,
                validator=f"{tool} lint",
                output=completed.stdout + "\n" + completed.stderr,
                duration_ms=duration_ms,
            )
        except FileNotFoundError:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return ValidationResult(success=True, validator=tool, output=f"{tool} not found, skipping", duration_ms=duration_ms)

    async def run_type_checker(self, repo_path: str, tool: str = "mypy") -> ValidationResult:
        import time

        start = time.perf_counter()
        try:
            completed = subprocess.run([tool, "."], cwd=repo_path, capture_output=True, text=True, timeout=120)
            duration_ms = int((time.perf_counter() - start) * 1000)
            return ValidationResult(
                success=completed.returncode == 0,
                validator=tool,
                output=completed.stdout + "\n" + completed.stderr,
                duration_ms=duration_ms,
            )
        except FileNotFoundError:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return ValidationResult(success=True, validator=tool, output=f"{tool} not found, skipping", duration_ms=duration_ms)

    async def validate_all(self, repo_path: str, checks: list[str] | None = None) -> dict[str, ValidationResult]:
        if not checks:
            checks = ["tests", "format", "lint"]

        results: dict[str, ValidationResult] = {}
        for check in checks:
            if check == "tests":
                results["tests"] = await self.run_tests(repo_path)
            elif check == "format":
                results["format"] = await self.run_formatter(repo_path)
            elif check == "lint":
                results["lint"] = await self.run_linter(repo_path)
            elif check == "typecheck":
                results["typecheck"] = await self.run_type_checker(repo_path)
        return results

    @property
    def all_passed(self) -> bool:
        return False  # placeholder, used externally
