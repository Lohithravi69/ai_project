from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.parsers.tree_sitter_parser import TreeSitterParser


class KnowledgeGraphBuilder:
    """Build a project knowledge graph by parsing files and extracting nodes and edges.

    This implementation writes directly to the `project_graph_nodes` and `project_graph_edges`
    tables created by the database init SQL.
    """

    def __init__(self) -> None:
        self._parser = TreeSitterParser()

    async def build_graph(self, session: AsyncSession, repository_id: str, repo_root: Path) -> dict[str, Any]:
        """Scan repository files and populate graph tables. Returns a simple map summary."""

        nodes_total = 0
        edges_total = 0

        for file_path in repo_root.rglob("*"):
            if not file_path.is_file():
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            parsed = self._parser.parse(file_path, content)
            counts = await self.sync_file(session, repository_id, file_path, parsed)
            nodes_total += counts["nodes"]
            edges_total += counts["edges"]

        await session.commit()

        return {"nodes": nodes_total, "edges": edges_total}

    async def delete_file(self, session: AsyncSession, repository_id: str, file_path: Path | str) -> None:
        canonical = str(file_path)
        await session.execute(
            text(
                "DELETE FROM project_graph_edges WHERE repository_id = :rid AND (from_node IN (SELECT node_id FROM project_graph_nodes WHERE repository_id = :rid AND canonical_path LIKE :prefix) OR to_node IN (SELECT node_id FROM project_graph_nodes WHERE repository_id = :rid AND canonical_path LIKE :prefix))"
            ),
            {"rid": repository_id, "prefix": f"{canonical}%"},
        )
        await session.execute(
            text("DELETE FROM project_graph_nodes WHERE repository_id = :rid AND canonical_path LIKE :prefix"),
            {"rid": repository_id, "prefix": f"{canonical}%"},
        )

    async def sync_file(self, session: AsyncSession, repository_id: str, file_path: Path, parsed: Any) -> dict[str, int]:
        await self.delete_file(session, repository_id, file_path)
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        file_node_id = str(uuid4())
        nodes.append(
            {
                "node_id": file_node_id,
                "repository_id": repository_id,
                "node_type": "file",
                "name": file_path.name,
                "canonical_path": str(file_path),
                "metadata_json": {"language": parsed.language, "symbols": parsed.symbols},
            }
        )

        for imp in parsed.imports:
            target_node_id = str(uuid4())
            nodes.append(
                {
                    "node_id": target_node_id,
                    "repository_id": repository_id,
                    "node_type": "import_ref",
                    "name": imp,
                    "canonical_path": imp,
                    "metadata_json": {},
                }
            )
            edges.append(
                {
                    "edge_id": str(uuid4()),
                    "repository_id": repository_id,
                    "from_node": file_node_id,
                    "to_node": target_node_id,
                    "edge_type": "imports",
                    "metadata_json": {},
                }
            )

        for fname in parsed.functions:
            func_node = str(uuid4())
            nodes.append(
                {
                    "node_id": func_node,
                    "repository_id": repository_id,
                    "node_type": "function",
                    "name": fname,
                    "canonical_path": f"{file_path}::{fname}",
                    "metadata_json": {},
                }
            )
            edges.append(
                {
                    "edge_id": str(uuid4()),
                    "repository_id": repository_id,
                    "from_node": file_node_id,
                    "to_node": func_node,
                    "edge_type": "defines",
                    "metadata_json": {},
                }
            )

        for cname in parsed.classes:
            class_node = str(uuid4())
            nodes.append(
                {
                    "node_id": class_node,
                    "repository_id": repository_id,
                    "node_type": "class",
                    "name": cname,
                    "canonical_path": f"{file_path}::{cname}",
                    "metadata_json": {},
                }
            )
            edges.append(
                {
                    "edge_id": str(uuid4()),
                    "repository_id": repository_id,
                    "from_node": file_node_id,
                    "to_node": class_node,
                    "edge_type": "defines",
                    "metadata_json": {},
                }
            )

        if nodes:
            await session.execute(
                text(
                    "INSERT INTO project_graph_nodes (node_id, repository_id, node_type, name, canonical_path, metadata_json, created_at) "
                    "VALUES (:node_id, :repository_id, :node_type, :name, :canonical_path, :metadata_json, CURRENT_TIMESTAMP)"
                ),
                [{**node, "metadata_json": json.dumps(node.get("metadata_json") or {})} for node in nodes],
            )
        if edges:
            await session.execute(
                text(
                    "INSERT INTO project_graph_edges (edge_id, repository_id, from_node, to_node, edge_type, metadata_json, created_at) "
                    "VALUES (:edge_id, :repository_id, :from_node, :to_node, :edge_type, :metadata_json, CURRENT_TIMESTAMP)"
                ),
                [{**edge, "metadata_json": json.dumps(edge.get("metadata_json") or {})} for edge in edges],
            )
        return {"nodes": len(nodes), "edges": len(edges)}

    async def generate_project_map(self, session: AsyncSession, repository_id: str, repo_root: Path) -> dict[str, Any]:
        """Generate a project_map.json with full structural overview."""
        nodes = []
        edges = []

        for file_path in repo_root.rglob("*"):
            if not file_path.is_file():
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            parsed = self._parser.parse(file_path, content)
            file_entry = {
                "path": str(file_path),
                "language": parsed.language,
                "functions": parsed.functions,
                "classes": parsed.classes,
                "imports": parsed.imports,
                "routes": parsed.routes,
            }
            nodes.append(file_entry)
            for imp in parsed.imports:
                edges.append({"from": str(file_path), "to": imp, "type": "imports"})

        project_map = {
            "repository_id": repository_id,
            "root": str(repo_root),
            "files": nodes,
            "dependencies": edges,
            "summary": {
                "total_files": len(nodes),
                "total_edges": len(edges),
            },
        }
        map_path = repo_root / "project_map.json"
        map_path.write_text(json.dumps(project_map, indent=2), encoding="utf-8")
        return project_map
