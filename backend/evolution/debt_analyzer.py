from __future__ import annotations

import re
from typing import Any


class DebtItem:
    def __init__(
        self,
        category: str,
        file_path: str,
        line_start: int = 0,
        line_end: int = 0,
        description: str = "",
        severity: str = "medium",
        metric_name: str = "",
        metric_value: float = 0.0,
        suggestion: str = "",
    ) -> None:
        self.category = category
        self.file_path = file_path
        self.line_start = line_start
        self.line_end = line_end
        self.description = description
        self.severity = severity
        self.metric_name = metric_name
        self.metric_value = metric_value
        self.suggestion = suggestion

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "description": self.description,
            "severity": self.severity,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "suggestion": self.suggestion,
        }


_GOD_CLASS_PATTERNS = [
    (r"class\s+(\w+)(?:\(.*\))?\s*:", "class_definition"),
    (r"def\s+\w+\s*\(", "method_definition"),
    (r"from\s+[\w.]+\s+import", "import_statement"),
    (r"self\.\w+\s*=", "field_assignment"),
]


class TechnicalDebtAnalyzer:
    def analyze_file(self, file_path: str, content: str) -> list[DebtItem]:
        items: list[DebtItem] = []
        lines = content.split("\n")
        total_lines = len(lines)

        if total_lines > 500:
            items.append(DebtItem(
                category="large_file",
                file_path=file_path,
                line_end=total_lines,
                description=f"File has {total_lines} lines, exceeding 500 line limit",
                severity="high" if total_lines > 1000 else "medium",
                metric_name="total_lines",
                metric_value=total_lines,
                suggestion="Split file into smaller focused modules",
            ))

        class_line = 0
        class_def = ""
        method_count = 0
        field_count = 0
        import_count = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            m = re.match(r"class\s+(\w+)", stripped)
            if m:
                if class_line and method_count > 10:
                    items.append(DebtItem(
                        category="god_class",
                        file_path=file_path,
                        line_start=class_line,
                        line_end=i,
                        description=f"Class '{class_def}' has {method_count} methods and {field_count} fields",
                        severity="high" if method_count > 20 else "medium",
                        metric_name="method_count",
                        metric_value=method_count,
                        suggestion="Split class using Single Responsibility Principle",
                    ))
                class_line = i
                class_def = m.group(1)
                method_count = 0
                field_count = 0
                import_count = 0

            if re.match(r"def\s+\w+\s*\(", stripped):
                method_count += 1

            if "self." in stripped and "=" in stripped:
                field_count += 1

            if re.match(r"from\s|import\s", stripped):
                import_count += 1

        if class_line and method_count > 10:
            items.append(DebtItem(
                category="god_class",
                file_path=file_path,
                line_start=class_line,
                description=f"Class '{class_def}' has {method_count} methods",
                severity="high" if method_count > 20 else "medium",
                metric_name="method_count",
                metric_value=method_count,
                suggestion="Extract related methods into separate classes",
            ))

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            m = re.match(r"def\s+(\w+)\s*\(", stripped)
            if m:
                method_body_start = i
                method_end = i
                for j in range(i, min(i + 100, len(lines) + 1)):
                    if j == len(lines):
                        break
                    if lines[j - 1].strip() and re.match(r"^\S", lines[j - 1].strip()) and not lines[j - 1].startswith(" " * 4) and not lines[j - 1].startswith("\t"):
                        method_end = j - 1
                        if method_end <= i:
                            method_end = i
                        break
                    method_end = j

                method_length = method_end - method_body_start + 1
                if method_length > 80:
                    items.append(DebtItem(
                        category="long_method",
                        file_path=file_path,
                        line_start=method_body_start,
                        line_end=method_end,
                        description=f"Method '{m.group(1)}' is {method_length} lines long",
                        severity="high" if method_length > 150 else "medium",
                        metric_name="method_length",
                        metric_value=method_length,
                        suggestion="Extract method into smaller focused functions",
                    ))

            if re.search(r"\bpass\s*#|#\s*TODO|#\s*FIXME|#\s*HACK|#\s*XXX", stripped):
                items.append(DebtItem(
                    category="dead_code",
                    file_path=file_path,
                    line_start=i,
                    description=f"Marker found: {stripped[:80]}",
                    severity="low",
                    metric_name="marker_count",
                    metric_value=1,
                    suggestion="Address or remove incomplete code",
                ))

            if re.match(r"^\s*#\s*TODO|^\s*#\s*FIXME", stripped, re.IGNORECASE):
                pass

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if re.search(r"(?:^|\.)(\w+)\s*=\s*(?:[\w.]+\s*=\s*)+", stripped):
                items.append(DebtItem(
                    category="duplicate_logic",
                    file_path=file_path,
                    line_start=i,
                    description=f"Chained assignment on line {i}",
                    severity="low",
                    metric_name="chain_assignments",
                    metric_value=1,
                    suggestion="Break into separate assignment statements",
                ))

        try:
            indent_levels: dict[int, int] = {}
            for i, line in enumerate(lines, 1):
                if stripped := line.strip():
                    indent = len(line) - len(stripped)
                    indent_levels[indent] = indent_levels.get(indent, 0) + 1
            max_indent = max(indent_levels.keys()) if indent_levels else 0
            if max_indent > 40:
                items.append(DebtItem(
                    category="high_complexity",
                    file_path=file_path,
                    description=f"Maximum indentation depth of {max_indent} spaces",
                    severity="medium",
                    metric_name="max_indent",
                    metric_value=max_indent,
                    suggestion="Extract deeply nested code into separate functions",
                ))
        except Exception:
            pass

        return items

    def analyze_files(self, files: dict[str, str]) -> list[DebtItem]:
        all_items: list[DebtItem] = []
        for path, content in files.items():
            all_items.extend(self.analyze_file(path, content))
        return all_items

    def generate_summary(self, items: list[DebtItem]) -> dict[str, Any]:
        by_category: dict[str, list[DebtItem]] = {}
        for item in items:
            by_category.setdefault(item.category, []).append(item)

        severity_weight = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        total_score = sum(
            severity_weight.get(item.severity, 1) for item in items
        )
        max_score = len(items) * 4

        categories = {}
        for cat, cat_items in by_category.items():
            cat_score = sum(severity_weight.get(i.severity, 1) for i in cat_items)
            categories[cat] = {
                "count": len(cat_items),
                "severity_score": cat_score,
                "items": [i.to_dict() for i in cat_items[:10]],
            }

        return {
            "total_items": len(items),
            "total_score": total_score,
            "max_score": max_score,
            "debt_ratio": round(total_score / max_score, 2) if max_score > 0 else 0,
            "categories": categories,
            "by_severity": {
                sev: len([i for i in items if i.severity == sev])
                for sev in ["critical", "high", "medium", "low"]
            },
        }
