from __future__ import annotations

import re
from typing import Any


class ArchChange:
    def __init__(
        self,
        change_type: str,
        description: str,
        rationale: str = "",
        affected_files: list[str] | None = None,
        severity: str = "medium",
        principle: str = "",
        confidence: float = 0.0,
    ) -> None:
        self.change_type = change_type
        self.description = description
        self.rationale = rationale
        self.affected_files = affected_files or []
        self.severity = severity
        self.principle = principle
        self.confidence = confidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "change_type": self.change_type,
            "description": self.description,
            "rationale": self.rationale,
            "affected_files": self.affected_files,
            "severity": self.severity,
            "principle": self.principle,
            "confidence": self.confidence,
        }


_SOLID_HEURISTICS: list[dict[str, Any]] = [
    {
        "principle": "Single Responsibility",
        "pattern": r"class\s+\w+.*:",
        "check": lambda cls_name, methods, fields: len(methods) > 15 or len(fields) > 20,
        "message": "Class '{cls}' has {methods} methods and {fields} fields — likely violates SRP",
        "severity": "high",
    },
    {
        "principle": "Open/Closed",
        "pattern": r"if\s+\w+\s*==\s*['\"]?\w+['\"]?|elif\s+\w+\s*==\s*['\"]?\w+['\"]?",
        "check": lambda name, count, _: count > 5,
        "message": "Multiple if/elif chains suggest Open/Closed violation — use polymorphism",
        "severity": "medium",
    },
    {
        "principle": "Dependency Inversion",
        "pattern": r"from\s+(backend\.\w+\.\w+)\s+import|import\s+(backend\.\w+\.\w+)",
        "check": lambda name, count, _: False,
        "message": "Direct import of concrete module '{mod}' — consider depending on abstractions",
        "severity": "low",
    },
]

_LAYER_SEPARATION_RULES: list[tuple[str, str, str, str]] = [
    (r"backend\.api.*", r"backend\.database\.models", "API layer imports database models directly", "high"),
    (r"backend\.api.*", r"backend\.embeddings", "API layer imports embedding layer directly", "medium"),
    (r"backend\.presentation.*", r"backend\.database", "Presentation layer imports database directly", "high"),
    (r"backend\.infrastructure.*", r"backend\.domain", "Infrastructure imports domain - consider dependency inversion", "low"),
]


class ArchitectureEvolutionEngine:
    def analyze_file(self, file_path: str, content: str, all_imports: list[str] | None = None) -> list[ArchChange]:
        changes: list[ArchChange] = []
        lines = content.split("\n")

        class_info: dict[str, tuple[int, int, list[str], list[str]]] = {}
        current_class: str | None = None
        methods: list[str] = []
        fields: list[str] = []
        start_line = 0

        for i, line in enumerate(lines, 1):
            m = re.match(r"class\s+(\w+)", line.strip())
            if m:
                if current_class and _SOLID_HEURISTICS[0]["check"](current_class, methods, fields):
                    _, _, _, _, msg_tmpl, sev = list(_SOLID_HEURISTICS[0].values())
                    changes.append(ArchChange(
                        change_type="srp_violation",
                        description=msg_tmpl.replace("{cls}", current_class).replace("{methods}", str(len(methods))).replace("{fields}", str(len(fields))),
                        affected_files=[file_path],
                        severity=sev,
                        principle="Single Responsibility",
                        confidence=0.7,
                    ))
                current_class = m.group(1)
                start_line = i
                methods = []
                fields = []

            if current_class:
                stripped = line.strip()
                if re.match(r"def\s+\w+\s*\(", stripped):
                    methods.append(stripped)
                if "self." in stripped and "=" in stripped:
                    fields.append(stripped)

        if current_class and _SOLID_HEURISTICS[0]["check"](current_class, methods, fields):
            changes.append(ArchChange(
                change_type="srp_violation",
                description=f"Class '{current_class}' has {len(methods)} methods and {len(fields)} fields — likely violates SRP",
                affected_files=[file_path],
                severity="high",
                principle="Single Responsibility",
                confidence=0.7,
            ))

        if_elif_count = 0
        for line in lines:
            if re.match(r"\s*(?:if|elif)\s+.+:", line.strip()):
                if_elif_count += 1
        if if_elif_count > 5:
            changes.append(ArchChange(
                change_type="ocp_violation",
                description=f"Multiple if/elif chains ({if_elif_count}) suggest Open/Closed violation",
                affected_files=[file_path],
                severity="medium",
                principle="Open/Closed",
                confidence=0.5,
            ))

        imports: list[tuple[int, str]] = []
        for i, line in enumerate(lines, 1):
            m = re.match(r"(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", line.strip())
            if m:
                mod = (m.group(1) or m.group(2) or "")
                imports.append((i, mod))

        for line_num, mod in imports:
            for layer_pattern, target_pattern, desc, sev in _LAYER_SEPARATION_RULES:
                if re.match(layer_pattern, file_path) and re.match(target_pattern, mod):
                    changes.append(ArchChange(
                        change_type="layer_violation",
                        description=f"{desc} ({mod})",
                        affected_files=[file_path],
                        severity=sev,
                        principle="Layered Architecture",
                        confidence=0.8,
                    ))

        return changes

    def analyze_files(self, files: dict[str, str]) -> list[ArchChange]:
        all_changes: list[ArchChange] = []
        all_imports: list[str] = []
        for path, content in files.items():
            for line in content.split("\n"):
                m = re.match(r"(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", line.strip())
                if m:
                    all_imports.append(m.group(1) or m.group(2))
            all_changes.extend(self.analyze_file(path, content, all_imports))
        return all_changes

    def generate_evolution_report(self, changes: list[ArchChange]) -> dict[str, Any]:
        by_principle: dict[str, list[ArchChange]] = {}
        for c in changes:
            by_principle.setdefault(c.principle, []).append(c)

        return {
            "total_changes": len(changes),
            "by_principle": {
                principle: {
                    "count": len(principle_changes),
                    "items": [c.to_dict() for c in principle_changes[:5]],
                }
                for principle, principle_changes in by_principle.items()
            },
            "layer_violations": len([c for c in changes if c.change_type == "layer_violation"]),
            "srp_violations": len([c for c in changes if c.change_type == "srp_violation"]),
            "ocp_violations": len([c for c in changes if c.change_type == "ocp_violation"]),
        }
