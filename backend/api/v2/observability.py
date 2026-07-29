from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database.session import engine, get_session
from backend.execution.celery_app import celery_app
from backend.monitoring.logging import logger
from backend.services.runtime_guard import RuntimeGuard

try:
    import psutil
except Exception:  # pragma: no cover - optional dependency fallback
    psutil = None


router = APIRouter(prefix="/api/v2", tags=["observability"])


class AgentExecutionOut(BaseModel):
    id: str
    repository_id: str | None = None
    agent_name: str
    task_name: str
    status: str
    step_logs: list[dict[str, Any]]
    metadata_json: dict[str, Any]
    error_message: str
    started_at: str
    finished_at: str | None = None
    duration_ms: int


class AgentObservabilityResponse(BaseModel):
    executions: list[AgentExecutionOut]
    task_queue: dict[str, Any]


class RetrievalLogOut(BaseModel):
    retrieval_id: str
    repository_id: str | None = None
    query_text: str | None = None
    query_meta: dict[str, Any]
    results: list[dict[str, Any]]
    top_k: int | None = None
    latency_ms: int | None = None
    created_at: str | None = None


class RetrievalObservabilityResponse(BaseModel):
    logs: list[RetrievalLogOut]


class UsageSummaryResponse(BaseModel):
    total_prompt_tokens: int
    total_completion_tokens: int
    avg_context_size: float
    avg_retrieved_chunks: float
    avg_response_time_ms: float
    recent_queries: int


class SystemHealthResponse(BaseModel):
    status: str
    dependencies: list[dict[str, Any]]
    workers: dict[str, Any]
    resources: dict[str, Any]


@router.get("/observability/agents", response_model=AgentObservabilityResponse)
async def agent_observability(session: AsyncSession = Depends(get_session)):
    executions_result = await session.execute(text("SELECT id, repository_id, agent_name, task_name, status, step_logs, metadata_json, error_message, started_at, finished_at, duration_ms FROM agent_executions ORDER BY started_at DESC LIMIT 100"))
    executions = [
        AgentExecutionOut(
            id=row["id"],
            repository_id=row["repository_id"],
            agent_name=row["agent_name"],
            task_name=row["task_name"],
            status=row["status"],
            step_logs=row.get("step_logs") or [],
            metadata_json=row.get("metadata_json") or {},
            error_message=row.get("error_message") or "",
            started_at=str(row.get("started_at")) if row.get("started_at") else "",
            finished_at=str(row.get("finished_at")) if row.get("finished_at") else None,
            duration_ms=int(row.get("duration_ms") or 0),
        )
        for row in executions_result.mappings().all()
    ]
    inspector = celery_app.control.inspect(timeout=2.0)
    if inspector is None:
        task_queue = {"active": {}, "reserved": {}, "scheduled": {}}
        return AgentObservabilityResponse(executions=executions, task_queue=task_queue)
    task_queue = {
        "active": inspector.active() or {},
        "reserved": inspector.reserved() or {},
        "scheduled": inspector.scheduled() or {},
    }
    return AgentObservabilityResponse(executions=executions, task_queue=task_queue)


@router.get("/observability/retrieval", response_model=RetrievalObservabilityResponse)
async def retrieval_observability(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        text(
            "SELECT retrieval_id, repository_id, query_text, query_meta, results, top_k, latency_ms, created_at FROM retrieval_logs ORDER BY created_at DESC LIMIT 100"
        )
    )
    logs = [
        RetrievalLogOut(
            retrieval_id=row["retrieval_id"],
            repository_id=row["repository_id"],
            query_text=row.get("query_text"),
            query_meta=row.get("query_meta") or {},
            results=row.get("results") or [],
            top_k=row.get("top_k"),
            latency_ms=row.get("latency_ms"),
            created_at=str(row.get("created_at")) if row.get("created_at") else None,
        )
        for row in result.mappings().all()
    ]
    return RetrievalObservabilityResponse(logs=logs)


@router.get("/observability/usage", response_model=UsageSummaryResponse)
async def usage_observability(session: AsyncSession = Depends(get_session)):
    result = await session.execute(text("SELECT query_meta FROM retrieval_logs ORDER BY created_at DESC LIMIT 250"))
    rows = result.mappings().all()
    if not rows:
        return UsageSummaryResponse(total_prompt_tokens=0, total_completion_tokens=0, avg_context_size=0.0, avg_retrieved_chunks=0.0, avg_response_time_ms=0.0, recent_queries=0)

    prompt_tokens = 0
    completion_tokens = 0
    context_sizes = []
    retrieved_chunks = []
    response_times = []
    for row in rows:
        meta = row.get("query_meta") or {}
        prompt_tokens += int(meta.get("prompt_tokens") or 0)
        completion_tokens += int(meta.get("completion_tokens") or 0)
        context_sizes.append(int(meta.get("context_size") or 0))
        retrieved_chunks.append(int(meta.get("retrieved_chunk_count") or 0))
        if row.get("query_meta"):
            response_times.append(int(meta.get("response_time_ms") or 0))

    return UsageSummaryResponse(
        total_prompt_tokens=prompt_tokens,
        total_completion_tokens=completion_tokens,
        avg_context_size=sum(context_sizes) / len(context_sizes),
        avg_retrieved_chunks=sum(retrieved_chunks) / len(retrieved_chunks),
        avg_response_time_ms=sum(response_times) / len(response_times) if response_times else 0.0,
        recent_queries=len(rows),
    )


@router.get("/system/health", response_model=SystemHealthResponse)
async def system_health(session: AsyncSession = Depends(get_session)):
    settings = get_settings()
    guard = RuntimeGuard(settings)
    dependencies = await guard.snapshot(engine)
    try:
        if psutil is None:
            raise RuntimeError("psutil is unavailable")
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        resources = {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_used_mb": round(memory.used / (1024 * 1024), 2),
            "memory_total_mb": round(memory.total / (1024 * 1024), 2),
            "disk_percent": disk.percent,
            "disk_used_gb": round(disk.used / (1024 * 1024 * 1024), 2),
            "disk_total_gb": round(disk.total / (1024 * 1024 * 1024), 2),
        }
    except Exception as exc:  # pragma: no cover - fallback for environments without psutil
        logger.warning(f"resource metrics unavailable: {exc}")
        resources = {"cpu_percent": None, "memory_percent": None, "disk_percent": None}

    inspector = celery_app.control.inspect(timeout=2.0)
    workers = {
        "active": inspector.active() if inspector else {},
        "stats": inspector.stats() if inspector else {},
        "registered": inspector.registered() if inspector else {},
    }
    status = "ok" if all(dep.status == "ok" for dep in dependencies) else "degraded"
    return SystemHealthResponse(status=status, dependencies=RuntimeGuard.as_dicts(dependencies), workers=workers, resources=resources)
