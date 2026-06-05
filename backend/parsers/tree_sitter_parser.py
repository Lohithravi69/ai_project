from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.config import get_settings
from backend.utils.files import detect_language

try:
    from tree_sitter import Language, Parser
except Exception:  # pragma: no cover - optional runtime dependency support
    Language = None
    Parser = None


FUNCTION_PATTERNS = {
    "python": re.compile(r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE),
    "javascript": re.compile(r"^\s*function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE),
    "typescript": re.compile(r"^\s*function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE),
    "tsx": re.compile(r"^\s*function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE),
    "java": re.compile(r"^\s*(?:public|private|protected)?\s*(?:static\s+)?[A-Za-z0-9_<>\[\]]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", re.MULTILINE),
}
CLASS_PATTERNS = {
    "python": re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[:\(]", re.MULTILINE),
    "javascript": re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{", re.MULTILINE),
    "typescript": re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{", re.MULTILINE),
    "tsx": re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{", re.MULTILINE),
    "java": re.compile(r"^\s*(?:public|private|protected)?\s*class\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE),
}
IMPORT_PATTERNS = {
    "python": re.compile(r"^\s*(?:from\s+([A-Za-z0-9_\.]+)\s+import|import\s+([A-Za-z0-9_\.]+))", re.MULTILINE),
    "javascript": re.compile(r"^\s*import\s+.*?from\s+['\"]([^'\"]+)['\"]", re.MULTILINE),
    "typescript": re.compile(r"^\s*import\s+.*?from\s+['\"]([^'\"]+)['\"]", re.MULTILINE),
    "tsx": re.compile(r"^\s*import\s+.*?from\s+['\"]([^'\"]+)['\"]", re.MULTILINE),
    "java": re.compile(r"^\s*import\s+([A-Za-z0-9_\.\*]+);", re.MULTILINE),
}
ROUTE_PATTERNS = [
    re.compile(r"@(?:app|router)\.(get|post|put|delete|patch)\([\"']([^\"']+)[\"']"),
    re.compile(r"(?:app|router)\.(get|post|put|delete|patch)\([\"']([^\"']+)[\"']"),
]


@dataclass
class ParsedFile:
    path: str
    language: str
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    routes: list[str] = field(default_factory=list)
    symbols: list[dict[str, Any]] = field(default_factory=list)


class TreeSitterParser:
    """Parse source files and extract code structure for repository understanding."""

    def __init__(self) -> None:
        settings = get_settings()
        self.language_library = settings.tree_sitter_language_library or ""
        self._parser = Parser() if Parser else None
        self._languages: dict[str, Any] = {}

    def _load_tree_sitter_language(self, language_name: str) -> Any | None:
        if not Language or not self.language_library:
            return None
        if language_name in self._languages:
            return self._languages[language_name]
        try:
            language = Language(self.language_library, language_name)
            self._languages[language_name] = language
            return language
        except Exception:
            return None

    def parse(self, file_path: Path, content: str) -> ParsedFile:
        language = detect_language(file_path)
        parsed = ParsedFile(path=str(file_path), language=language)

        if self._parser and self._load_tree_sitter_language(language):
            # Tree-sitter integration is used when a compiled language bundle is provided.
            try:
                self._parser.set_language(self._load_tree_sitter_language(language))
                self._parser.parse(content.encode("utf-8", errors="ignore"))
            except Exception:
                pass

        parsed.functions = self._extract_matches(content, FUNCTION_PATTERNS.get(language))
        parsed.classes = self._extract_matches(content, CLASS_PATTERNS.get(language))
        parsed.imports = self._extract_imports(content, IMPORT_PATTERNS.get(language))
        parsed.routes = self._extract_routes(content)
        parsed.symbols = self._build_symbol_payload(parsed)
        return parsed

    @staticmethod
    def _extract_matches(content: str, pattern: re.Pattern[str] | None) -> list[str]:
        if not pattern:
            return []
        return [match.group(1) for match in pattern.finditer(content) if match.group(1)]

    @staticmethod
    def _extract_imports(content: str, pattern: re.Pattern[str] | None) -> list[str]:
        if not pattern:
            return []
        results: list[str] = []
        for match in pattern.finditer(content):
            groups = [group for group in match.groups() if group]
            results.extend(groups)
        return results

    @staticmethod
    def _extract_routes(content: str) -> list[str]:
        routes: list[str] = []
        for pattern in ROUTE_PATTERNS:
            for match in pattern.finditer(content):
                if len(match.groups()) == 2:
                    routes.append(f"{match.group(1).upper()} {match.group(2)}")
                else:
                    routes.append(match.group(1))
        return routes

    @staticmethod
    def _build_symbol_payload(parsed: ParsedFile) -> list[dict[str, Any]]:
        symbols: list[dict[str, Any]] = []
        symbols.extend({"kind": "function", "name": name} for name in parsed.functions)
        symbols.extend({"kind": "class", "name": name} for name in parsed.classes)
        symbols.extend({"kind": "import", "name": name} for name in parsed.imports)
        symbols.extend({"kind": "route", "name": name} for name in parsed.routes)
        return symbols
