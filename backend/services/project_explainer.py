from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import models as db_models
from backend.embeddings.ollama_client import OllamaClient
from backend.services.knowledge_graph import KnowledgeGraphBuilder


class ProjectExplainer:
    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama
        self._kg = KnowledgeGraphBuilder()

    async def explain_repository(self, session: AsyncSession, repository_id: str, repo_root: Path | None = None) -> Dict[str, Any]:
        # If repo_root provided, rebuild graph; otherwise read existing nodes/edges
        if repo_root:
            await self._kg.build_graph(session, repository_id, repo_root)

        nodes_res = await session.execute(select(db_models.__dict__["project_graph_nodes"])) if "project_graph_nodes" in db_models.__dict__ else None
        # Fallback: simple summary via Ollama
        prompt = f"Explain the architecture and main components of repository {repository_id}. Provide layers and key files."
        explanation = await self.ollama.chat([{"role": "system", "content": "You are an expert that explains code architectures."}, {"role": "user", "content": prompt}])
        return {"explanation": explanation}
