from __future__ import annotations

import re
from typing import Any


class SecurityFinding:
    def __init__(
        self,
        finding_type: str,
        description: str,
        file_path: str = "",
        line_number: int = 0,
        severity: str = "high",
        cwe: str = "",
        suggestion: str = "",
    ) -> None:
        self.finding_type = finding_type
        self.description = description
        self.file_path = file_path
        self.line_number = line_number
        self.severity = severity
        self.cwe = cwe
        self.suggestion = suggestion

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_type": self.finding_type,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "severity": self.severity,
            "cwe": self.cwe,
            "suggestion": self.suggestion,
        }


_SECURITY_PATTERNS: list[tuple[str, str, str, str, str]] = [
    (r"""(?i)(?:api_key|api_secret|password|secret|token|credential|auth_token)\s*=\s*['\"][^'"]{4,}['\"]""",
     "hardcoded_secret", "Hardcoded secret/credential in source code",
     "critical", "CWE-798", "Move to environment variables or a secrets manager"),

    (r"os\.system\s*\(", "shell_execution",
     "Shell execution via os.system()", "high", "CWE-78",
     "Use subprocess.run with shell=False"),

    (r"subprocess\.\w+\s*\(.*shell\s*=\s*True", "shell_execution",
     "Shell execution with shell=True", "high", "CWE-78",
     "Use shell=False and pass args as a list"),

    (r"eval\s*\(", "code_injection",
     "Dynamic code evaluation via eval()", "critical", "CWE-95",
     "Avoid eval() — use safer alternatives"),

    (r"exec\s*\(", "code_injection",
     "Dynamic code execution via exec()", "critical", "CWE-95",
     "Avoid exec() — use safer alternatives"),

    (r"pickle\.loads?\s*\(", "unsafe_deserialization",
     "Unsafe deserialization via pickle", "high", "CWE-502",
     "Use JSON or a safe serialization format"),

    (r"yaml\.load\s*\((?!.*Loader=yaml\.SafeLoader)", "unsafe_deserialization",
     "Unsafe YAML load() without SafeLoader", "high", "CWE-502",
     "Use yaml.safe_load() instead"),

    (r"sqlite3\.execute\s*\(.*f['\"]|sqlite3\.execute\s*\(.*['\"]\s*\+", "sql_injection",
     "Potential SQL injection via f-string or concatenation", "critical", "CWE-89",
     "Use parameterized queries with ? placeholders"),

    (r"execute\s*\(.*f['\"]|execute\s*\(.*['\"]\s*\+", "sql_injection",
     "Potential SQL injection in DB query", "critical", "CWE-89",
     "Use parameterized queries with placeholders"),

    (r"\.format\(.*\{.*input|f['\"].*\{.*input", "template_injection",
     "User input in format string — potential injection", "medium", "CWE-94",
     "Validate and escape user input"),

    (r"mark_safe\s*\(|safe\s*\)", "xss",
     "Content marked as safe HTML — potential XSS", "high", "CWE-79",
     "Avoid marking user content as safe"),

    (r"__repr__|__str__.*return.*f['\"]|__repr__|__str__.*return.*\.format", "information_leak",
     "Potential information leakage via repr/str", "low", "CWE-200",
     "Avoid including sensitive data in string representations"),

    (r"render\(.*request.*\{", "template_context",
     "Template rendering with request data — verify no sensitive leakage", "low", "CWE-200",
     "Review template context for sensitive data"),

    (r"os\.environ\s*\[|os\.environ\.get\s*\(", "env_access",
     "Environment variable access — ensure secrets not logged", "low", "", "Avoid logging environment variables"),

    (r"@app\.route|@router\.(get|post|put|delete)", "api_endpoint",
     "API endpoint definition — verify authentication required", "medium", "",
     "Ensure endpoints are protected by authentication middleware"),
]

_XSS_HTML_PATTERNS: list[str] = [
    r"<script[^>]*>",
    r"onerror\s*=",
    r"onclick\s*=",
    r"onload\s*=",
    r"javascript\s*:",
]


class SecurityAdvisor:
    def analyze_file(self, file_path: str, content: str) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("/*"):
                continue

            for pattern, ftype, desc, sev, cwe, suggestion in _SECURITY_PATTERNS:
                try:
                    if re.search(pattern, stripped):
                        findings.append(SecurityFinding(
                            finding_type=ftype,
                            description=desc,
                            file_path=file_path,
                            line_number=i,
                            severity=sev,
                            cwe=cwe,
                            suggestion=suggestion,
                        ))
                except re.error:
                    continue

            if file_path.endswith((".html", ".jsx", ".tsx", ".vue")):
                for xss_pat in _XSS_HTML_PATTERNS:
                    if re.search(xss_pat, stripped, re.IGNORECASE):
                        findings.append(SecurityFinding(
                            finding_type="xss",
                            description=f"Potential XSS vulnerability: {stripped[:80]}",
                            file_path=file_path,
                            line_number=i,
                            severity="high",
                            cwe="CWE-79",
                            suggestion="Use safe rendering methods and escape user input",
                        ))

        return findings

    def analyze_files(self, files: dict[str, str]) -> list[SecurityFinding]:
        all_findings: list[SecurityFinding] = []
        for path, content in files.items():
            all_findings.extend(self.analyze_file(path, content))
        return all_findings

    def generate_summary(self, findings: list[SecurityFinding]) -> dict[str, Any]:
        by_type: dict[str, list[SecurityFinding]] = {}
        for f in findings:
            by_type.setdefault(f.finding_type, []).append(f)

        severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        critical = len([f for f in findings if f.severity == "critical"])
        high = len([f for f in findings if f.severity == "high"])
        medium = len([f for f in findings if f.severity == "medium"])
        low = len([f for f in findings if f.severity == "low"])

        return {
            "total_findings": len(findings),
            "by_severity": {"critical": critical, "high": high, "medium": medium, "low": low},
            "risk_score": min(10, critical * 3 + high * 2 + medium * 0.5),
            "by_type": {
                ftype: {
                    "count": len(ftype_findings),
                    "items": [f.to_dict() for f in ftype_findings[:5]],
                }
                for ftype, ftype_findings in by_type.items()
            },
        }
