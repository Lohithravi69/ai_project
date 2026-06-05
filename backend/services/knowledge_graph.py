from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import insert, select
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

        nodes_map: dict[str, str] = {}  # canonical -> node_id
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        for file_path in repo_root.rglob("*"):
            if not file_path.is_file():
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            parsed = self._parser.parse(file_path, content)

            # file node
            file_node_id = str(uuid4())
            nodes_map[str(file_path)] = file_node_id
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

            # imports -> edges
            for imp in parsed.imports:
                target = imp
                # create a node for the import reference (best-effort)
                target_node_id = nodes_map.get(target) or str(uuid4())
                nodes_map[target] = target_node_id
                nodes.append(
                    {
                        "node_id": target_node_id,
                        "repository_id": repository_id,
                        "node_type": "import_ref",
                        "name": target,
                        "canonical_path": target,
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

            # functions/classes as nodes
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

        # deduplicate nodes by node_id (SQL will enforce pk uniqueness)
        # bulk insert nodes and edges
        if nodes:
            await session.execute(insert("project_graph_nodes"), nodes)
        if edges:
            await session.execute(insert("project_graph_edges"), edges)

        await session.commit()

        return {"nodes": len(nodes), "edges": len(edges)}
