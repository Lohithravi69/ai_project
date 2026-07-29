from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ObservabilityService:
    async def start_agent_execution(
        self,
        session: AsyncSession,
        repository_id: str | None,
        agent_name: str,
        task_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        execution_id = str(uuid4())
        await session.execute(
            text(
                "INSERT INTO agent_executions (id, repository_id, agent_name, task_name, status, step_logs, metadata_json, error_message, started_at, finished_at, duration_ms, created_at, updated_at) "
                "VALUES (:id, :repository_id, :agent_name, :task_name, 'running', '[]'::jsonb, CAST(:metadata_json AS jsonb), '', NOW(), NULL, 0, NOW(), NOW())"
            ),
            {
                "id": execution_id,
                "repository_id": repository_id,
                "agent_name": agent_name,
                "task_name": task_name,
                "metadata_json": json.dumps(metadata or {}),
            },
        )
        await session.commit()
        return execution_id

    async def append_step(
        self,
        session: AsyncSession,
        execution_id: str,
        step_name: str,
        status: str,
        detail: str = "",
    ) -> None:
        await session.execute(
            text(
                "UPDATE agent_executions SET step_logs = COALESCE(step_logs, '[]'::jsonb) || jsonb_build_array(jsonb_build_object('step', :step_name, 'status', :status, 'detail', :detail, 'ts', NOW())), updated_at = NOW() WHERE id = :id"
            ),
            {"id": execution_id, "step_name": step_name, "status": status, "detail": detail},
        )
        await session.commit()

    async def finish_agent_execution(
        self,
        session: AsyncSession,
        execution_id: str,
        status: str,
        error_message: str = "",
    ) -> None:
        await session.execute(
            text(
                "UPDATE agent_executions SET status = :status, error_message = :error_message, finished_at = NOW(), duration_ms = CAST(EXTRACT(EPOCH FROM (NOW() - started_at)) * 1000 AS INTEGER), updated_at = NOW() WHERE id = :id"
            ),
            {"id": execution_id, "status": status, "error_message": error_message},
        )
        await session.commit()

    async def log_retrieval(
        self,
        session: AsyncSession,
        repository_id: str | None,
        query_text: str,
        query_meta: dict[str, Any],
        results: list[dict[str, Any]],
        top_k: int,
        latency_ms: int,
    ) -> None:
        await session.execute(
            text(
                "INSERT INTO retrieval_logs (retrieval_id, repository_id, query_text, query_meta, results, top_k, latency_ms, created_at) "
                "VALUES (:retrieval_id, :repository_id, :query_text, CAST(:query_meta AS jsonb), CAST(:results AS jsonb), :top_k, :latency_ms, NOW())"
            ),
            {
                "retrieval_id": str(uuid4()),
                "repository_id": repository_id,
                "query_text": query_text,
                "query_meta": json.dumps(query_meta),
                "results": json.dumps(results),
                "top_k": top_k,
                "latency_ms": latency_ms,
            },
        )
        await session.commit()
