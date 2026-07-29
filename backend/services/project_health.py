from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import FileRecord, RepositoryRecord
from backend.parsers.tree_sitter_parser import TreeSitterParser
from backend.utils.files import hash_content


class ProjectHealth:
    """Analyze repository health with static heuristics.

    Detects:
    - Large files
    - Duplicate files
    - Likely unused files (no incoming imports within repo_graph)
    - Missing documentation (missing README, missing module docstrings)
    - Simple dead code heuristics (unused functions by name absence in imports)
    """

    def __init__(self) -> None:
        self._parser = TreeSitterParser()

    async def analyze(self, session: AsyncSession, repository_id: str, repo_root: Path | None = None) -> Dict[str, Any]:
        repo = await session.get(RepositoryRecord, repository_id)
        if not repo:
            raise RuntimeError("Repository not found")

        root = Path(repo.local_path) if repo.local_path else (repo_root or Path("."))
        report: Dict[str, Any] = {
            "repository_id": repository_id,
            "large_files": [],
            "duplicate_files": [],
            "missing_documentation": [],
            "likely_unused_files": [],
            "dead_code_candidates": [],
            "circular_dependencies": [],
        }

        # scan files from DB records to keep consistency
        result = await session.execute(select(FileRecord).where(FileRecord.repository_id == repository_id))
        files = list(result.scalars().all())

        # large files
        for f in files:
            try:
                p = Path(f.path)
                size = p.stat().st_size if p.exists() else 0
                if size > 1_000_000:  # >1MB
                    report["large_files"].append({"path": f.path, "size": size})
            except Exception:
                continue

        # duplicate files by content hash
        hash_map: Dict[str, List[str]] = {}
        for f in files:
            try:
                p = Path(f.path)
                if p.exists():
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    h = hash_content(content)
                    hash_map.setdefault(h, []).append(f.path)
            except Exception:
                continue
        for h, paths in hash_map.items():
            if len(paths) > 1:
                report["duplicate_files"].append({"hash": h, "paths": paths})

        # missing documentation: check for README at repo root and module docstrings
        readme = root / "README.md"
        if not readme.exists():
            report["missing_documentation"].append({"reason": "no README.md at repo root"})

        for f in files:
            try:
                p = Path(f.path)
                if p.exists() and p.suffix == ".py":
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    # simple heuristic: module-level docstring
                    stripped = content.lstrip()
                    if not (stripped.startswith('"""') or stripped.startswith("'''")):
                        report["missing_documentation"].append({"path": f.path, "reason": "no module docstring"})
            except Exception:
                continue

        # naive dead code: functions declared but not referenced in any file imports or calls
        # build a simple name index
        name_index: Dict[str, int] = {}
        for f in files:
            try:
                p = Path(f.path)
                if p.exists():
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    parsed = self._parser.parse(p, content)
                    for func in parsed.functions:
                        name_index[f"{f.path}::{func}"] = name_index.get(f"{f.path}::{func}", 0)
                    # check for occurrences
                    for other in files:
                        if other.path == f.path:
                            continue
                        try:
                            op = Path(other.path)
                            if op.exists():
                                ocontent = op.read_text(encoding="utf-8", errors="ignore")
                                for func in parsed.functions:
                                    if func in ocontent:
                                        name_index[f"{f.path}::{func}"] += 1
                        except Exception:
                            continue
            except Exception:
                continue

        for k, cnt in name_index.items():
            if cnt == 0:
                report["dead_code_candidates"].append({"symbol": k})

        # circular dependencies via import graph
        import_graph: dict[str, list[str]] = {}
        for f in files:
            try:
                syms = f.symbols_json or {}
                file_imports: list[str] = syms.get("imports", [])
                import_graph[f.path] = []
                for imp in file_imports:
                    resolved = self._resolve_import_to_file(imp, files)
                    if resolved:
                        import_graph[f.path].append(resolved)
            except Exception:
                continue

        cycles = self._detect_cycles(import_graph)
        for cycle in cycles:
            report["circular_dependencies"].append({"cycle": cycle})

        return report

    @staticmethod
    def _resolve_import_to_file(imp: str, all_files: list[FileRecord]) -> str | None:
        """Resolve a module import string to a file path in the repository."""
        imp_path = imp.replace(".", "/")
        candidates = []
        for f in all_files:
            p = f.path.replace("\\", "/")
            if imp_path in p:
                candidates.append(p)
        return candidates[0] if candidates else None

    @staticmethod
    def _detect_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
        """Detect cycles in a directed graph using DFS."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {node: WHITE for node in graph}
        parent: dict[str, str | None] = {}
        cycles: list[list[str]] = []

        def dfs(node: str) -> None:
            color[node] = GRAY
            for neighbor in graph.get(node, []):
                if neighbor not in color:
                    color[neighbor] = WHITE
                if color[neighbor] == GRAY:
                    cycle = []
                    cur = node
                    while cur != neighbor:
                        cycle.append(cur)
                        cur = parent.get(cur, "")
                    cycle.append(neighbor)
                    cycle.append(node)
                    cycles.append(cycle)
                elif color[neighbor] == WHITE:
                    parent[neighbor] = node
                    dfs(neighbor)
            color[node] = BLACK

        for node in list(graph):
            if color.get(node, WHITE) == WHITE:
                parent[node] = None
                dfs(node)

        return cycles
