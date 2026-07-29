from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.orchestrator import AgentOrchestrator
from backend.autonomous import (
    AutonomousTaskEngine,
    FailureAnalyzer,
    ArchitectureAdvisor,
    ReportGenerator,
)
from backend.database.models import (
    AutonomousTaskRecord,
    FailureAnalysisRecord,
    RepairAttemptRecord,
    TaskProgressRecord,
    ExecutionReportRecord,
    ArchitectureRecommendationRecord,
)
from backend.database.session import get_session
from backend.models.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    AgentStatusResponse,
    AutonomousTaskCreate,
    AutonomousTaskRead,
    AutonomousTaskList,
    AutonomousTaskAction,
    FailureAnalysisSchema,
    ArchitectureRecommendationSchema,
    EngineeringReportSchema,
    AgentScoringRequest,
)

router = APIRouter(prefix="/api/v6", tags=["autonomous"])


def _task_to_read(task: AutonomousTaskRecord) -> AutonomousTaskRead:
    return AutonomousTaskRead(
        id=task.id,
        objective=task.objective,
        status=task.status,
        mode=task.mode,
        repository_id=task.repository_id or "",
        plan_id=task.plan_id or "",
        result_summary=task.result_summary,
        error_message=task.error_message,
        repair_attempts=task.repair_attempts,
        max_repair_attempts=task.max_repair_attempts,
        progress=task.progress_json.get("steps", []),
        analyses=[],
        metrics=task.metrics_json,
        celery_task_id=task.celery_task_id,
        created_at=str(task.created_at) if task.created_at else "",
        updated_at=str(task.updated_at) if task.updated_at else "",
    )


_engine = AutonomousTaskEngine()
_failure_analyzer = FailureAnalyzer()
_architecture_advisor = ArchitectureAdvisor()
_report_generator = ReportGenerator()


# ── Autonomous Task CRUD ────────────────────────────────────────────────────


@router.post("/tasks", response_model=AutonomousTaskRead)
async def create_task(payload: AutonomousTaskCreate, session: AsyncSession = Depends(get_session)):
    task_id = _engine.create_task(
        objective=payload.objective,
        mode=payload.mode,
        repository_id=payload.repository_id,
        max_repair_attempts=payload.max_repair_attempts,
    )
    record = AutonomousTaskRecord(
        id=task_id,
        objective=payload.objective,
        status="pending",
        mode=payload.mode,
        repository_id=payload.repository_id or None,
        max_repair_attempts=payload.max_repair_attempts,
        progress_json={"steps": []},
        metrics_json={"created_at": 0},
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return _task_to_read(record)


@router.get("/tasks", response_model=AutonomousTaskList)
async def list_tasks(
    status: str | None = Query(None),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    query = select(AutonomousTaskRecord).order_by(AutonomousTaskRecord.created_at.desc()).limit(limit)
    if status:
        query = query.where(AutonomousTaskRecord.status == status)
    result = await session.execute(query)
    records = list(result.scalars().all())
    return AutonomousTaskList(
        tasks=[_task_to_read(r) for r in records],
        total=len(records),
    )


@router.get("/tasks/{task_id}", response_model=AutonomousTaskRead)
async def get_task(task_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(AutonomousTaskRecord).where(AutonomousTaskRecord.id == task_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")
    task = _engine.get_task(task_id)
    if task:
        record.progress_json = {"steps": task.get("progress", [])}
        record.metrics_json = task.get("metrics", record.metrics_json)
    return _task_to_read(record)


@router.post("/tasks/{task_id}/action")
async def task_action(task_id: str, payload: AutonomousTaskAction):
    if payload.action == "cancel":
        ok = _engine.cancel_task(task_id)
    elif payload.action == "pause":
        task = _engine.get_task(task_id)
        if task:
            task["status"] = "paused"
            ok = True
        else:
            ok = False
    elif payload.action == "resume":
        ok = _engine.start_task(task_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {payload.action}")
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "ok", "task_id": task_id, "action": payload.action}


# ── Autonomous Execution ────────────────────────────────────────────────────


@router.post("/tasks/{task_id}/execute", response_model=AgentRunResponse)
async def execute_task(task_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(AutonomousTaskRecord).where(AutonomousTaskRecord.id == task_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")
    if record.status not in ("pending", "paused"):
        raise HTTPException(status_code=400, detail=f"Task is {record.status}, not pending/paused")

    _engine.start_task(task_id)
    record.status = "running"
    await session.commit()

    orchestrator = AgentOrchestrator(session)
    run_request = AgentRunRequest(
        request_text=record.objective,
        repository_id=record.repository_id or "",
        mode=record.mode,
    )
    try:
        response = await orchestrator.run_full_pipeline(run_request)
        _engine.complete_task(task_id, result_summary=response.result_summary)
        record.status = "completed"
        record.result_summary = response.result_summary
        record.plan_id = response.plan_id
        record.metrics_json["total_duration_ms"] = sum(
            t.duration_ms for t in response.agent_trace
        )
        for trace in response.agent_trace:
            progress_entry = TaskProgressRecord(
                task_id=task_id,
                agent_name=trace.agent_name,
                stage="execution",
                status="completed" if trace.success else "failed",
                message=trace.output_summary,
                duration_ms=trace.duration_ms,
                details_json={
                    "input": trace.input_summary,
                    "ai_reasoning": trace.ai_reasoning.model_dump() if trace.ai_reasoning else {},
                },
            )
            session.add(progress_entry)
    except Exception as exc:
        record.status = "failed"
        record.error_message = str(exc)
        _engine.complete_task(task_id, status="failed")
        response = AgentRunResponse(
            execution_id=task_id,
            status="failed",
            result_summary=str(exc),
        )

    await session.commit()
    return response


# ── Failure Analysis ────────────────────────────────────────────────────────


@router.post("/analyze/failures", response_model=list[FailureAnalysisSchema])
async def analyze_failures(errors: list[str]):
    analyses = _failure_analyzer.analyze_batch(errors)
    return [FailureAnalysisSchema(
        category=a.category.value,
        severity=a.severity,
        summary=a.summary,
        details=a.details,
        recovery_strategies=[s.to_dict() for s in a.recovery_strategies],
    ) for a in analyses]


@router.get("/tasks/{task_id}/analyses", response_model=list[FailureAnalysisSchema])
async def get_task_analyses(task_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(FailureAnalysisRecord).where(FailureAnalysisRecord.task_id == task_id)
    )
    records = list(result.scalars().all())
    return [FailureAnalysisSchema(
        category=r.category,
        severity=r.severity,
        summary=r.summary,
        details=r.details_json,
        recovery_strategies=[],
    ) for r in records]


# ── Architecture Advisor ────────────────────────────────────────────────────


@router.post("/analyze/architecture", response_model=list[ArchitectureRecommendationSchema])
async def analyze_architecture(files: dict[str, str]):
    all_recs: list[ArchitectureRecommendationSchema] = []
    for file_path, content in files.items():
        recs = _architecture_advisor.analyze_code_quality(file_path, content)
        for r in recs:
            all_recs.append(ArchitectureRecommendationSchema(
                title=r.title,
                category=r.category,
                description=r.description,
                affected_files=r.affected_files,
                confidence=r.confidence,
            ))
    ranked = _architecture_advisor.rank_recommendations(
        [r for r in _architecture_advisor.analyze_code_quality.__doc__ or []]
    ) if False else []
    return all_recs


# ── Engineering Report ──────────────────────────────────────────────────────


@router.post("/tasks/{task_id}/report", response_model=EngineeringReportSchema)
async def generate_report(task_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(AutonomousTaskRecord).where(AutonomousTaskRecord.id == task_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")

    progress_result = await session.execute(
        select(TaskProgressRecord).where(TaskProgressRecord.task_id == task_id)
    )
    progress_records = list(progress_result.scalars().all())

    analyses_result = await session.execute(
        select(FailureAnalysisRecord).where(FailureAnalysisRecord.task_id == task_id)
    )
    analysis_records = list(analyses_result.scalars().all())

    progress_data = [
        {
            "agent_name": p.agent_name,
            "stage": p.stage,
            "status": p.status,
            "message": p.message,
            "duration_ms": p.duration_ms,
            "score": p.score,
        }
        for p in progress_records
    ]

    analysis_data = [
        {
            "category": a.category,
            "severity": a.severity,
            "summary": a.summary,
            "details": a.details_json,
        }
        for a in analysis_records
    ]

    report = _report_generator.generate_execution_report(
        objective=record.objective,
        task_progress=progress_data,
        analyses=analysis_data,
        repair_attempts=record.repair_attempts,
        metrics=record.metrics_json,
    )

    report_record = ExecutionReportRecord(
        task_id=task_id,
        plan_id=record.plan_id,
        title=report.title,
        summary=report.summary,
        sections_json=[s.to_dict() for s in report.sections],
        metrics_json=report.metrics,
        recommendations_json=report.recommendations,
    )
    session.add(report_record)
    await session.commit()

    return EngineeringReportSchema(
        title=report.title,
        report_type=report.report_type,
        summary=report.summary,
        sections=[s.to_dict() for s in report.sections],
        metrics=report.metrics,
        recommendations=report.recommendations,
        generated_at=report.generated_at,
    )


@router.get("/reports", response_model=list[EngineeringReportSchema])
async def list_reports(
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ExecutionReportRecord).order_by(ExecutionReportRecord.created_at.desc()).limit(limit)
    )
    records = list(result.scalars().all())
    return [EngineeringReportSchema(
        title=r.title,
        report_type=r.report_type,
        summary=r.summary,
        sections=r.sections_json,
        metrics=r.metrics_json,
        recommendations=r.recommendations_json,
    ) for r in records]


# ── Agent Scoring ────────────────────────────────────────────────────────────


@router.post("/agents/score")
async def score_agent(payload: AgentScoringRequest):
    from backend.learning.evaluator import SelfEvaluator

    evaluator = SelfEvaluator()
    score = evaluator.evaluate_agent(
        agent_name=payload.agent_name,
        success=len([r for r in payload.tool_responses if r.get("success")]) > 0,
        error_count=len(payload.errors),
        tool_call_count=len(payload.tool_responses),
    )
    return score.to_dict()


# ── Experience / Pattern Search (Capabilities 5 & 6) ────────────────────────


@router.get("/patterns", response_model=list[dict[str, Any]])
async def list_patterns(category: str | None = Query(None)):
    from backend.learning.pattern_store import PatternStore

    store = PatternStore()
    patterns = store.list_patterns(category=category)
    return [p.to_dict() for p in patterns]


@router.get("/patterns/search", response_model=list[dict[str, Any]])
async def search_patterns(q: str = Query(min_length=1)):
    from backend.learning.pattern_store import PatternStore

    store = PatternStore()
    patterns = store.search_patterns(q)
    return [p.to_dict() for p in patterns]


@router.get("/experiences/search", response_model=list[dict[str, Any]])
async def search_experiences(q: str = Query(min_length=1)):
    from backend.learning.experience_store import ExperienceStore

    store = ExperienceStore()
    results = store.search(q)
    return [{"similarity": sim, **r.to_dict()} for r, sim in results]
