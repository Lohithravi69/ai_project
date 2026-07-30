from __future__ import annotations

import re
from typing import Any


class PerfFinding:
    def __init__(
        self,
        finding_type: str,
        description: str,
        file_path: str = "",
        line_number: int = 0,
        severity: str = "medium",
        impact: str = "",
        suggestion: str = "",
    ) -> None:
        self.finding_type = finding_type
        self.description = description
        self.file_path = file_path
        self.line_number = line_number
        self.severity = severity
        self.impact = impact
        self.suggestion = suggestion

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_type": self.finding_type,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "severity": self.severity,
            "impact": self.impact,
            "suggestion": self.suggestion,
        }


_SLOW_PATTERNS: list[tuple[str, str, str, str, str]] = [
    (r"for\s+\w+\s+in\s+\w+:\s*\n\s+for\s+\w+\s+in\s+\w+:", "nested_loop", "Nested for-loop detected — O(n²) complexity", "high", "Replace with dictionary lookup or set intersection"),
    (r"\.append\(.*\)\s*\n\s+\.append\(", "repeated_append", "Repeated .append() calls — consider list comprehension", "low", "Use list comprehension for better performance"),
    (r"time\.sleep\s*\(", "blocking_io", "time.sleep() blocks the event loop", "high", "Use asyncio.sleep() in async code"),
    (r"requests\.(get|post|put|delete)\s*\(", "sync_http", "Synchronous HTTP call blocks event loop", "high", "Use httpx.AsyncClient instead of requests"),
    (r"while\s+True\s*:", "infinite_loop", "Infinite while loop — ensure exit condition", "medium", "Add a break condition or timeout"),
    (r"os\.path\.exists\s*\(|os\.path\.isfile\s*\(|os\.path\.isdir\s*\(", "repeated_stat", "Repeated filesystem stat calls", "medium", "Cache stat results or use pathlib"),
    (r"for\s+\w+\s+in\s+range\(\s*len\(", "c_style_loop", "C-style for loop — use direct iteration", "low", "Iterate directly over the collection"),
    (r"\.join\(\s*\[.*for.*\]\s*\)", "join_gen", "str.join with list comprehension — use generator", "low", "Remove brackets to use generator expression"),
    (r"\.all\(\)\s*$", "query_all", ".all() fetches all rows — consider pagination", "medium", "Add LIMIT/OFFSET or use streaming"),
]


class PerformanceAdvisor:
    def analyze_file(self, file_path: str, content: str) -> list[PerfFinding]:
        findings: list[PerfFinding] = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            for pattern, ftype, desc, sev, suggestion in _SLOW_PATTERNS:
                m = re.search(pattern, line, re.IGNORECASE)
                if m:
                    findings.append(PerfFinding(
                        finding_type=ftype,
                        description=desc,
                        file_path=file_path,
                        line_number=i,
                        severity=sev,
                        impact=desc,
                        suggestion=suggestion,
                    ))

        total_imports = len([l for l in lines if re.match(r"^(?:from|import)\s", l.strip())])
        total_functions = len([l for l in lines if re.match(r"^def\s+\w+\s*\(", l.strip())])
        if total_imports > 20 and total_functions > 0:
            findings.append(PerfFinding(
                finding_type="slow_import",
                description=f"File imports {total_imports} modules — slow startup time",
                file_path=file_path,
                severity="low",
                impact="Increases application startup time",
                suggestion="Defer imports with local imports inside functions",
            ))

        return findings

    def analyze_files(self, files: dict[str, str]) -> list[PerfFinding]:
        all_findings: list[PerfFinding] = []
        for path, content in files.items():
            all_findings.extend(self.analyze_file(path, content))
        return all_findings

    def generate_summary(self, findings: list[PerfFinding]) -> dict[str, Any]:
        by_type: dict[str, list[PerfFinding]] = {}
        for f in findings:
            by_type.setdefault(f.finding_type, []).append(f)

        severity_order = {"high": 3, "medium": 2, "low": 1}
        high = len([f for f in findings if f.severity == "high"])
        medium = len([f for f in findings if f.severity == "medium"])
        low = len([f for f in findings if f.severity == "low"])

        return {
            "total_findings": len(findings),
            "by_severity": {"high": high, "medium": medium, "low": low},
            "score": max(0, 10 - high * 2 - medium * 0.5),
            "by_type": {
                ftype: {
                    "count": len(ftype_findings),
                    "items": [f.to_dict() for f in ftype_findings[:5]],
                }
                for ftype, ftype_findings in by_type.items()
            },
        }
