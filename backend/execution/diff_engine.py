from __future__ import annotations

import re
from difflib import unified_diff
from pathlib import Path
from typing import Any

from backend.utils.files import safe_read_text


class DiffEngine:
    def unified(self, old_content: str, new_content: str, file_path: str = "file") -> str:
        return "\n".join(
            unified_diff(
                old_content.splitlines(),
                new_content.splitlines(),
                fromfile=file_path,
                tofile=f"{file_path} (modified)",
                lineterm="",
            )
        )

    def side_by_side(self, old_content: str, new_content: str, context: int = 3) -> str:
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        result: list[str] = []
        max_len = 60
        result.append(f"{'OLD':<{max_len}} | {'NEW':<{max_len}}")
        result.append(f"{'-'*max_len}-+-{'-'*max_len}")

        import difflib

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == "equal":
                for k in range(i1, i2):
                    result.append(f"{old_lines[k]:<{max_len}} | {new_lines[k]:<{max_len}}")
            elif op == "replace":
                max_replace = max(i2 - i1, j2 - j1)
                for k in range(max_replace):
                    old_line = old_lines[i1 + k] if i1 + k < i2 else ""
                    new_line = new_lines[j1 + k] if j1 + k < j2 else ""
                    result.append(f"{'> ' + old_line:<{max_len}} | {'< ' + new_line:<{max_len}}")
            elif op == "delete":
                for k in range(i1, i2):
                    result.append(f"{'- ' + old_lines[k]:<{max_len}} | {'':<{max_len}}")
            elif op == "insert":
                for k in range(j1, j2):
                    result.append(f"{'':<{max_len}} | {'+ ' + new_lines[k]:<{max_len}}")
        return "\n".join(result)

    def file_summary(self, old_content: str, new_content: str, file_path: str = "file") -> dict[str, Any]:
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        import difflib

        added = 0
        deleted = 0
        modified_functions: list[str] = []

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == "insert":
                added += j2 - j1
            elif op == "delete":
                deleted += i2 - i1
            elif op == "replace":
                added += j2 - j1
                deleted += i2 - i1

        # Detect modified functions by scanning for function definitions
        func_pattern = re.compile(r"^\s*(async\s+)?def\s+\w+|^\s*(export\s+)?(function|class)\s+\w+")
        for line in old_lines + new_lines:
            if func_pattern.match(line):
                name = line.strip().split("(")[0].split("def ")[-1].split("class ")[-1].split("function ")[-1].split("export ")[-1].strip()
                if name and name not in modified_functions:
                    modified_functions.append(name)

        return {
            "file_path": file_path,
            "old_lines": len(old_lines),
            "new_lines": len(new_lines),
            "added_lines": added,
            "deleted_lines": deleted,
            "net_change": added - deleted,
            "modified_functions": modified_functions,
        }

    def compare_files(self, old_path: Path, new_path: Path) -> dict[str, Any]:
        old_content = safe_read_text(old_path) or ""
        new_content = safe_read_text(new_path) or ""
        return {
            "unified": self.unified(old_content, new_content, str(old_path.name)),
            "side_by_side": self.side_by_side(old_content, new_content),
            "file_summary": self.file_summary(old_content, new_content, str(old_path.name)),
        }

    def compare_strings(self, old_content: str, new_content: str, file_path: str = "file") -> dict[str, Any]:
        summary = self.file_summary(old_content, new_content, file_path)
        return {
            "unified": self.unified(old_content, new_content, file_path),
            "side_by_side": self.side_by_side(old_content, new_content),
            "file_summary": summary,
            "added_lines": summary["added_lines"],
            "deleted_lines": summary["deleted_lines"],
            "modified_functions": summary["modified_functions"],
            "estimated_impact": self._estimate_impact(summary),
        }

    def _estimate_impact(self, summary: dict[str, Any]) -> str:
        total_changes = summary["added_lines"] + summary["deleted_lines"]
        modified = len(summary.get("modified_functions", []))
        if total_changes > 500 or modified > 10:
            return "high"
        if total_changes > 100 or modified > 3:
            return "medium"
        if total_changes > 0:
            return "low"
        return "none"
