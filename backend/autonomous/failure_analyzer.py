from __future__ import annotations

import re
from enum import Enum
from typing import Any


class FailureCategory(str, Enum):
    COMPILATION = "compilation"
    SYNTAX = "syntax"
    RUNTIME = "runtime"
    DEPENDENCY = "dependency"
    TEST = "test"
    ARCHITECTURE = "architecture"
    PERFORMANCE = "performance"
    SECURITY = "security"
    ENVIRONMENT = "environment"
    GIT = "git"
    UNKNOWN = "unknown"


class RecoveryAction:
    def __init__(
        self,
        strategy: str,
        command_type: str = "",
        command_params: dict[str, Any] | None = None,
        description: str = "",
    ) -> None:
        self.strategy = strategy
        self.command_type = command_type
        self.command_params = command_params or {}
        self.description = description

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "command_type": self.command_type,
            "command_params": self.command_params,
            "description": self.description,
        }


_RECOVERY_STRATEGIES: dict[FailureCategory, list[RecoveryAction]] = {
    FailureCategory.COMPILATION: [
        RecoveryAction("Fix syntax in affected files", "read_file", {"pattern": "file"}, "Read and fix the reported compilation error"),
        RecoveryAction("Re-run compilation after fix", "run_command", {"command": "python -m py_compile <file>"}, "Verify compilation passes"),
    ],
    FailureCategory.SYNTAX: [
        RecoveryAction("Parse error details and fix syntax", "read_file", {"pattern": "file"}, "Read the file around the error line"),
        RecoveryAction("Apply syntax correction", "edit_file", {}, "Fix the syntax issue"),
    ],
    FailureCategory.RUNTIME: [
        RecoveryAction("Add error handling around failing call", "read_file", {"pattern": "file"}, "Read the file to understand context"),
        RecoveryAction("Wrap with try/except and log", "edit_file", {}, "Add defensive error handling"),
    ],
    FailureCategory.DEPENDENCY: [
        RecoveryAction("Install missing dependency", "run_command", {"command": "pip install <package>"}, "Install the required package"),
        RecoveryAction("Sync requirements file", "run_command", {"command": "pip freeze > requirements.txt"}, "Update requirements"),
    ],
    FailureCategory.TEST: [
        RecoveryAction("Read test failure output", "run_command", {"command": "pytest <test_file> -v --tb=short"}, "Get detailed test failure info"),
        RecoveryAction("Fix test or implementation", "edit_file", {}, "Correct the test or the code under test"),
    ],
    FailureCategory.ARCHITECTURE: [
        RecoveryAction("Review module structure", "list_directory", {}, "Understand current architecture"),
        RecoveryAction("Refactor to match pattern", "edit_file", {}, "Apply architectural correction"),
    ],
    FailureCategory.PERFORMANCE: [
        RecoveryAction("Profile hot path", "run_command", {"command": "python -m cProfile <script>"}, "Profile and identify bottleneck"),
        RecoveryAction("Optimize identified bottleneck", "edit_file", {}, "Apply performance fix"),
    ],
    FailureCategory.SECURITY: [
        RecoveryAction("Audit input validation", "grep", {"pattern": "input|request"}, "Find untrusted input entry points"),
        RecoveryAction("Add sanitization or validation", "edit_file", {}, "Apply security fix"),
    ],
    FailureCategory.ENVIRONMENT: [
        RecoveryAction("Check environment config", "run_command", {"command": "python -c 'import sys; print(sys.version)'"}, "Verify environment"),
        RecoveryAction("Update environment or config", "edit_file", {}, "Fix environment configuration"),
    ],
    FailureCategory.GIT: [
        RecoveryAction("Check git status", "run_command", {"command": "git status"}, "Understand git state"),
        RecoveryAction("Resolve merge conflict or retry", "run_command", {"command": "git merge --abort"}, "Reset and retry"),
    ],
    FailureCategory.UNKNOWN: [
        RecoveryAction("Collect diagnostic info", "run_command", {"command": "python -c 'import sys; print(sys.version_info)'"}, "Gather system info"),
        RecoveryAction("Escalate to developer", "run_command", {}, "Manual intervention required"),
    ],
}


class FailureAnalysis:
    def __init__(
        self,
        category: FailureCategory,
        severity: str,
        summary: str,
        details: dict[str, Any] | None = None,
        recovery_strategies: list[RecoveryAction] | None = None,
    ) -> None:
        self.category = category
        self.severity = severity
        self.summary = summary
        self.details = details or {}
        self.recovery_strategies = recovery_strategies or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "severity": self.severity,
            "summary": self.summary,
            "details": self.details,
            "recovery_strategies": [s.to_dict() for s in self.recovery_strategies],
        }


class FailureAnalyzer:
    CATEGORY_PATTERNS: dict[FailureCategory, list[str]] = {
        FailureCategory.COMPILATION: [
            r"(SyntaxError|IndentationError)",
            r"compile\s*error",
        ],
        FailureCategory.SYNTAX: [
            r"invalid\s*syntax",
            r"unexpected\s*eof",
            r"EOL\s*while",
            r"expected\s*':|;|,|\}|\]|\)",
        ],
        FailureCategory.RUNTIME: [
            r"(TypeError|ValueError|KeyError|IndexError|AttributeError|NameError)",
            r"zerodivision",
            r"stopiteration",
            r"runtime\s*error",
        ],
        FailureCategory.DEPENDENCY: [
            r"(ModuleNotFoundError|ImportError)",
            r"no\s*module\s*named",
            r"cannot\s*(find|import)",
            r"pip\s*install",
        ],
        FailureCategory.TEST: [
            r"(AssertionError|assert)",
            r"test\s*failed",
            r"pytest|unittest",
            r"FAILED\s*test",
        ],
        FailureCategory.ARCHITECTURE: [
            r"circular\s*import|circular\s*dependency",
            r"architecture",
            r"coupling",
            r"layering",
        ],
        FailureCategory.PERFORMANCE: [
            r"timeout|time\s*out",
            r"slow|performance",
            r"memory\s*error",
            r"OOM|out\s*of\s*memory",
        ],
        FailureCategory.SECURITY: [
            r"sql\s*injection|XSS|CSRF",
            r"injection|escape|sanitize",
            r"security|vulnerability",
        ],
        FailureCategory.ENVIRONMENT: [
            r"connection\s*refused|connection\s*reset",
            r"permission\s*denied",
            r"no\s*such\s*file|filenotfound",
            r"environment",
        ],
        FailureCategory.GIT: [
            r"merge\s*conflict",
            r"git\s*error|git:\s*",
            r"branch\s*not\s*found",
            r"commit\s*failed",
        ],
    }

    SEVERITY_KEYWORDS: dict[str, list[str]] = {
        "critical": ["fatal", "crash", "security", "data_loss", "corruption", "panic"],
        "high": ["error", "failure", "exception", "timeout", "merge conflict"],
        "medium": ["warning", "deprecated", "slow", "unexpected"],
        "low": ["info", "minor", "cosmetic", "style"],
    }

    def categorize(self, error_message: str, context: str = "") -> FailureCategory:
        combined = f"{error_message} {context}".lower()
        for category, patterns in self.CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, combined, re.IGNORECASE):
                    return category
        return FailureCategory.UNKNOWN

    def assess_severity(self, error_message: str, context: str = "") -> str:
        combined = f"{error_message} {context}".lower()
        for severity, keywords in self.SEVERITY_KEYWORDS.items():
            for kw in keywords:
                if kw in combined:
                    return severity
        return "medium"

    def analyze(self, error_message: str, context: str = "", details: dict[str, Any] | None = None) -> FailureAnalysis:
        category = self.categorize(error_message, context)
        severity = self.assess_severity(error_message, context)
        strategies = _RECOVERY_STRATEGIES.get(category, _RECOVERY_STRATEGIES[FailureCategory.UNKNOWN])
        return FailureAnalysis(
            category=category,
            severity=severity,
            summary=error_message[:500],
            details=details or {},
            recovery_strategies=strategies,
        )

    def analyze_batch(self, errors: list[str], context: str = "") -> list[FailureAnalysis]:
        return [self.analyze(err, context) for err in errors]
