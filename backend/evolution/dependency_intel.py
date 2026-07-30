from __future__ import annotations

import re
from typing import Any


class DepRecommendation:
    def __init__(
        self,
        package: str,
        current_version: str = "",
        suggested_version: str = "",
        severity: str = "medium",
        category: str = "outdated",
        description: str = "",
        upgrade_path: str = "",
        breaking: bool = False,
    ) -> None:
        self.package = package
        self.current_version = current_version
        self.suggested_version = suggested_version
        self.severity = severity
        self.category = category
        self.description = description
        self.upgrade_path = upgrade_path
        self.breaking = breaking

    def to_dict(self) -> dict[str, Any]:
        return {
            "package": self.package,
            "current_version": self.current_version,
            "suggested_version": self.suggested_version,
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
            "upgrade_path": self.upgrade_path,
            "breaking": self.breaking,
        }


_KNOWN_PACKAGES: dict[str, dict[str, Any]] = {
    "fastapi": {"latest": "0.115.0", "breaking": False, "security": False, "category": "framework"},
    "uvicorn": {"latest": "0.32.0", "breaking": False, "security": False, "category": "server"},
    "sqlalchemy": {"latest": "2.0.36", "breaking": False, "security": False, "category": "orm"},
    "alembic": {"latest": "1.13.3", "breaking": False, "security": False, "category": "migration"},
    "pydantic": {"latest": "2.9.0", "breaking": False, "security": False, "category": "validation"},
    "pytest": {"latest": "8.3.0", "breaking": False, "security": False, "category": "testing"},
    "celery": {"latest": "5.4.0", "breaking": False, "security": False, "category": "task_queue"},
    "redis": {"latest": "5.2.0", "breaking": False, "security": False, "category": "cache"},
    "httpx": {"latest": "0.28.0", "breaking": False, "security": False, "category": "http"},
    "aiohttp": {"latest": "3.10.0", "breaking": False, "security": False, "category": "http"},
    "requests": {"latest": "2.32.3", "breaking": False, "security": False, "category": "http"},
    "click": {"latest": "8.1.7", "breaking": False, "security": False, "category": "cli"},
    "jinja2": {"latest": "3.1.4", "breaking": False, "security": False, "category": "templating"},
    "pyyaml": {"latest": "6.0.2", "breaking": False, "security": False, "category": "serialization"},
    "numpy": {"latest": "2.1.0", "breaking": True, "security": False, "category": "numerical"},
    "pandas": {"latest": "2.2.0", "breaking": False, "security": False, "category": "data"},
    "boto3": {"latest": "1.35.0", "breaking": False, "security": False, "category": "aws"},
    "botocore": {"latest": "1.35.0", "breaking": False, "security": False, "category": "aws"},
    "aiofiles": {"latest": "24.1.0", "breaking": False, "security": False, "category": "io"},
    "python-multipart": {"latest": "0.0.12", "breaking": False, "security": False, "category": "upload"},
    "python-jose": {"latest": "3.3.0", "breaking": False, "security": False, "category": "auth"},
    "passlib": {"latest": "1.7.4", "breaking": False, "security": False, "category": "auth"},
    "bcrypt": {"latest": "4.2.0", "breaking": False, "security": False, "category": "auth"},
    "cryptography": {"latest": "43.0.0", "breaking": False, "security": True, "category": "security"},
    "pydantic-settings": {"latest": "2.5.0", "breaking": False, "security": False, "category": "config"},
    "python-dotenv": {"latest": "1.0.1", "breaking": False, "security": False, "category": "config"},
    "sentry-sdk": {"latest": "2.15.0", "breaking": False, "security": False, "category": "monitoring"},
    "prometheus-client": {"latest": "0.21.0", "breaking": False, "security": False, "category": "monitoring"},
    "loguru": {"latest": "0.7.2", "breaking": True, "security": False, "category": "logging"},
    "ruff": {"latest": "0.6.0", "breaking": False, "security": False, "category": "linting"},
    "mypy": {"latest": "1.12.0", "breaking": True, "security": False, "category": "type_checking"},
    "black": {"latest": "24.8.0", "breaking": True, "security": False, "category": "formatting"},
    "isort": {"latest": "5.13.2", "breaking": False, "security": False, "category": "formatting"},
    "coverage": {"latest": "7.6.0", "breaking": False, "security": False, "category": "testing"},
    "pre-commit": {"latest": "3.8.0", "breaking": False, "security": False, "category": "ci"},
}


class DependencyIntelligence:
    def analyze_requirements(self, content: str) -> list[DepRecommendation]:
        recommendations: list[DepRecommendation] = []
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            m = re.match(r"([\w\-_.]+)\s*(?:[=~><]+\s*(\d+\.\d+(?:\.\d+)?))?", line)
            if not m:
                continue
            pkg = m.group(1).lower()
            current_ver = m.group(2) or "unknown"
            known = _KNOWN_PACKAGES.get(pkg)
            if known:
                if current_ver != "unknown" and current_ver != known["latest"]:
                    try:
                        cur_parts = [int(x) for x in current_ver.split(".")]
                        latest_parts = [int(x) for x in known["latest"].split(".")]
                        major_diff = latest_parts[0] - cur_parts[0] if cur_parts else 0
                        severity = "high" if major_diff >= 2 else ("medium" if major_diff >= 1 else "low")
                    except (ValueError, IndexError):
                        severity = "medium"

                    desc = f"{pkg} {current_ver} → {known['latest']}"
                    if known["security"]:
                        desc += " (includes security fixes)"
                        severity = "high"

                    recommendations.append(DepRecommendation(
                        package=pkg,
                        current_version=current_ver,
                        suggested_version=known["latest"],
                        severity=severity,
                        category="outdated",
                        description=desc,
                        upgrade_path=f"{pkg}>={known['latest']}",
                        breaking=known["breaking"],
                    ))
            else:
                recommendations.append(DepRecommendation(
                    package=pkg,
                    current_version=current_ver,
                    severity="low",
                    category="unknown",
                    description=f"Unknown package '{pkg}' — verify it's still maintained",
                    upgrade_path="",
                ))
        return recommendations

    def analyze_imports(self, imports: list[str]) -> list[DepRecommendation]:
        recommendations: list[DepRecommendation] = []
        available = set(v.replace("_", "-") for v in _KNOWN_PACKAGES)
        for imp in imports:
            parts = imp.split(".")
            top_module = parts[0] if parts else ""
            std_lib_modules = {
                "os", "sys", "re", "json", "pathlib", "typing", "collections",
                "datetime", "math", "random", "itertools", "functools", "enum",
                "abc", "io", "base64", "hashlib", "hmac", "uuid", "copy",
                "inspect", "traceback", "logging", "warnings", "contextlib",
                "dataclasses", "threading", "asyncio", "concurrent", "subprocess",
                "tempfile", "shutil", "glob", "fnmatch", "textwrap", "string",
                "decimal", "fractions", "statistics", "operator",
            }
            if top_module in std_lib_modules:
                continue
            if top_module not in available:
                recommendations.append(DepRecommendation(
                    package=top_module,
                    severity="low",
                    category="unlisted",
                    description=f"'{top_module}' imported but not found in requirements — may be missing dependency",
                    upgrade_path=f"pip install {top_module}",
                ))
        return recommendations

    def generate_upgrade_plan(self, recommendations: list[DepRecommendation]) -> dict[str, Any]:
        breaking = [r for r in recommendations if r.breaking]
        safe = [r for r in recommendations if not r.breaking and r.category == "outdated"]

        return {
            "total": len(recommendations),
            "breaking_count": len(breaking),
            "safe_count": len(safe),
            "has_breaking": bool(breaking),
            "breaking_changes": [r.to_dict() for r in breaking],
            "safe_upgrades": [r.to_dict() for r in safe],
            "order": ["safe"] + (["breaking"] if breaking else []),
            "recommendation": (
                "Upgrade safe packages first, then plan breaking changes separately"
                if breaking else "All upgrades are safe — proceed in any order"
            ),
        }
