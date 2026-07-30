from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import RecommendationRecord, DebtItemRecord, VersionPlanRecord, AnalyticsTrendRecord, RepositoryRecord
from backend.database.session import get_session
from backend.evolution import (
    TechnicalDebtAnalyzer,
    ArchitectureEvolutionEngine,
    DependencyIntelligence,
    PerformanceAdvisor,
    SecurityAdvisor,
    VersionEvolutionPlanner,
    AnalyticsTracker,
    RecommendationCenter,
)
from backend.models.schemas import (
    AnalyzeFilesRequest,
    RequirementsRequest,
    ImportsRequest,
    FullAnalysisRequest,
    FullAnalysisResponse,
    VersionPlanRequest,
    RecommendationAction,
)

router = APIRouter(prefix="/api/v7", tags=["evolution"])

_debt = TechnicalDebtAnalyzer()
_arch = ArchitectureEvolutionEngine()
_dep = DependencyIntelligence()
_perf = PerformanceAdvisor()
_sec = SecurityAdvisor()
_vp = VersionEvolutionPlanner()
_at = AnalyticsTracker()
_rc = RecommendationCenter()


# ── DB helpers ────────────────────────────────────────────────────────────────


async def _persist_debt_items(session: AsyncSession, items: list[dict[str, Any]], execution_id: str = "") -> None:
    for item in items:
        record = DebtItemRecord(
            category=item.get("category", "unknown")[:64],
            file_path=item.get("file_path", ""),
            line_start=item.get("line_start", 0),
            line_end=item.get("line_end", 0),
            description=item.get("description", ""),
            severity=item.get("severity", "medium"),
            metric_name=item.get("metric_name", ""),
            metric_value=float(item.get("metric_value", 0)),
            suggestion=item.get("suggestion", ""),
            status="open",
            execution_id=execution_id or None,
        )
        session.add(record)
    await session.commit()


async def _persist_recommendation(session: AsyncSession, rec: Any) -> None:
    record = RecommendationRecord(
        id=rec.id,
        category=rec.category[:64],
        title=rec.title[:255],
        description=rec.description,
        severity=rec.severity,
        priority=rec.priority,
        status=rec.status,
        rationale=rec.rationale,
        effort_estimate=rec.effort_estimate,
        affected_files_json=rec.affected_files,
        metadata_json=rec.metadata,
    )
    session.add(record)
    await session.commit()


async def _persist_recommendations(session: AsyncSession, recs: list[Any]) -> None:
    for rec in recs:
        record = RecommendationRecord(
            id=rec.id,
            category=rec.category[:64],
            title=rec.title[:255],
            description=rec.description,
            severity=rec.severity,
            priority=rec.priority,
            status=rec.status,
            rationale=rec.rationale,
            effort_estimate=rec.effort_estimate,
            affected_files_json=rec.affected_files,
            metadata_json=rec.metadata,
        )
        session.add(record)
    await session.commit()


async def _persist_version_plan(session: AsyncSession, plan: Any, execution_id: str = "") -> None:
    record = VersionPlanRecord(
        current_version=plan.current_version,
        suggested_version=plan.suggested_version,
        title=plan.title,
        summary=plan.summary,
        reasons_json=plan.reasons,
        changes_json=plan.changes,
        risks_json=plan.risks,
        estimated_effort=plan.estimated_effort,
        status="proposed",
        execution_id=execution_id or None,
    )
    session.add(record)
    await session.commit()


async def _persist_trend(session: AsyncSession, snapshot: Any, repository_id: str = "") -> None:
    record = AnalyticsTrendRecord(
        metric_name=snapshot.metric_name,
        metric_value=snapshot.metric_value,
        metric_unit=snapshot.metric_unit,
        direction=snapshot.direction,
        change_percent=snapshot.change_percent,
        repository_id=repository_id or None,
        snapshot_json=snapshot.metadata or {},
    )
    session.add(record)
    await session.commit()


async def _update_rec_status(session: AsyncSession, rec_id: str, status: str) -> bool:
    result = await session.execute(
        select(RecommendationRecord).where(RecommendationRecord.id == rec_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        return False
    record.status = status
    if status == "approved":
        record.approved_at = datetime.now(timezone.utc)
    await session.commit()
    return True


# ── Technical Debt Analyzer ─────────────────────────────────────────────────


@router.post("/analyze/debt")
async def analyze_debt(payload: AnalyzeFilesRequest, session: AsyncSession = Depends(get_session)):
    items = _debt.analyze_files(payload.files)
    summary = _debt.generate_summary(items)
    item_dicts = [i.to_dict() for i in items]
    await _persist_debt_items(session, item_dicts)
    return {"items": item_dicts, "summary": summary}


@router.post("/analyze/debt/file")
async def analyze_debt_file(file_path: str = Query(...), content: str = Query(...)):
    items = _debt.analyze_file(file_path, content)
    summary = _debt.generate_summary(items)
    return {"items": [i.to_dict() for i in items], "summary": summary}


# ── Architecture Evolution Engine ──────────────────────────────────────────


@router.post("/analyze/architecture")
async def analyze_architecture(payload: AnalyzeFilesRequest):
    changes = _arch.analyze_files(payload.files)
    report = _arch.generate_evolution_report(changes)
    return {"changes": [c.to_dict() for c in changes], "report": report}


# ── Dependency Intelligence ────────────────────────────────────────────────


@router.post("/analyze/dependencies/requirements")
async def analyze_dependencies_req(payload: RequirementsRequest):
    recs = _dep.analyze_requirements(payload.content)
    plan = _dep.generate_upgrade_plan(recs)
    return {"recommendations": [r.to_dict() for r in recs], "upgrade_plan": plan}


@router.post("/analyze/dependencies/imports")
async def analyze_dependencies_imports(payload: ImportsRequest):
    recs = _dep.analyze_imports(payload.imports)
    return {"recommendations": [r.to_dict() for r in recs]}


# ── Performance Advisor ────────────────────────────────────────────────────


@router.post("/analyze/performance")
async def analyze_performance(payload: AnalyzeFilesRequest):
    findings = _perf.analyze_files(payload.files)
    summary = _perf.generate_summary(findings)
    return {"findings": [f.to_dict() for f in findings], "summary": summary}


# ── Security Advisor ────────────────────────────────────────────────────────


@router.post("/analyze/security")
async def analyze_security(payload: AnalyzeFilesRequest):
    findings = _sec.analyze_files(payload.files)
    summary = _sec.generate_summary(findings)
    return {"findings": [f.to_dict() for f in findings], "summary": summary}


# ── Full Analysis ──────────────────────────────────────────────────────────


@router.post("/analyze/full", response_model=FullAnalysisResponse)
async def analyze_full(payload: FullAnalysisRequest, session: AsyncSession = Depends(get_session)):
    debt_items = _debt.analyze_files(payload.files)
    debt_summary = _debt.generate_summary(debt_items)

    arch_changes = _arch.analyze_files(payload.files)
    arch_report = _arch.generate_evolution_report(arch_changes)

    dep_recs = _dep.analyze_requirements(payload.requirements_content)
    dep_plan = _dep.generate_upgrade_plan(dep_recs)
    import_recs = _dep.analyze_imports(payload.imports)
    all_dep_recs = [r.to_dict() for r in dep_recs + import_recs]

    perf_findings = _perf.analyze_files(payload.files)
    perf_summary = _perf.generate_summary(perf_findings)

    sec_findings = _sec.analyze_files(payload.files)
    sec_summary = _sec.generate_summary(sec_findings)

    version_plan = _vp.generate_plan(
        current_version=payload.current_version,
        debt_summary=debt_summary,
        arch_changes=[c.to_dict() for c in arch_changes],
        dep_recs=all_dep_recs,
        perf_findings=[f.to_dict() for f in perf_findings],
        sec_findings=[f.to_dict() for f in sec_findings],
    )

    recs = []
    recs.extend(_rc.add_from_debt([i.to_dict() for i in debt_items]))
    recs.extend(_rc.add_from_arch([c.to_dict() for c in arch_changes]))
    recs.extend(_rc.add_from_deps(all_dep_recs))
    recs.extend(_rc.add_from_perf([f.to_dict() for f in perf_findings]))
    recs.extend(_rc.add_from_security([f.to_dict() for f in sec_findings]))
    recommendations = _rc.get_by_priority()

    debt_snap = _at.record("debt_score", debt_summary.get("total_score", 0), "points")
    perf_snap = _at.record("perf_score", perf_summary.get("score", 10), "points")
    sec_snap = _at.record("sec_risk", sec_summary.get("risk_score", 0), "points")

    debt_item_dicts = [i.to_dict() for i in debt_items]
    await _persist_debt_items(session, debt_item_dicts)

    all_center_recs = _rc._recommendations
    await _persist_recommendations(session, all_center_recs[-len(recs):] if recs else [])

    await _persist_version_plan(session, version_plan)
    await _persist_trend(session, debt_snap)
    await _persist_trend(session, perf_snap)
    await _persist_trend(session, sec_snap)

    return FullAnalysisResponse(
        debt_summary=debt_summary,
        arch_report=arch_report,
        dep_plan=dep_plan,
        perf_summary=perf_summary,
        sec_summary=sec_summary,
        version_plan=version_plan.to_dict(),
        recommendations=recommendations,
    )


# ── Version Evolution Planner ──────────────────────────────────────────────


@router.post("/plan/version")
async def plan_version(payload: VersionPlanRequest, session: AsyncSession = Depends(get_session)):
    plan = _vp.generate_plan(
        current_version=payload.current_version,
        debt_summary=payload.debt_summary or None,
        arch_changes=payload.arch_changes or None,
        dep_recs=payload.dep_recs or None,
        perf_findings=payload.perf_findings or None,
        sec_findings=payload.sec_findings or None,
    )
    await _persist_version_plan(session, plan)
    return plan.to_dict()


# ── Repository Analytics ────────────────────────────────────────────────────


@router.get("/analytics/trends")
async def get_trends(metric: str | None = Query(None), session: AsyncSession = Depends(get_session)):
    if metric:
        rows = await session.execute(
            select(AnalyticsTrendRecord)
            .where(AnalyticsTrendRecord.metric_name == metric)
            .order_by(AnalyticsTrendRecord.created_at.desc())
            .limit(10)
        )
        return {"metric": metric, "data": [{"value": r.metric_value, "unit": r.metric_unit, "direction": r.direction, "change_percent": r.change_percent} for r in rows.scalars().all()]}
    return _at.get_summary()


@router.post("/analytics/record")
async def record_metric(
    metric_name: str = Query(...),
    value: float = Query(...),
    unit: str = Query(default=""),
    repository_id: str = Query(default=""),
    session: AsyncSession = Depends(get_session),
):
    snapshot = _at.record(metric_name, value, unit)
    await _persist_trend(session, snapshot, repository_id)
    return snapshot.to_dict()


# ── Recommendation Center ────────────────────────────────────────────────────


@router.get("/recommendations")
async def list_recommendations(
    status: str | None = Query(None),
    grouped: bool = Query(False),
    session: AsyncSession = Depends(get_session),
):
    if grouped:
        return _rc.get_grouped()
    return [r.to_dict() for r in _rc.get_all(status=status)]


@router.get("/recommendations/priority")
async def recommendations_by_priority():
    return _rc.get_by_priority()


@router.get("/recommendations/stats")
async def recommendation_stats():
    return _rc.get_stats()


@router.post("/recommendations/{rec_id}/action")
async def recommendation_action(rec_id: str, payload: RecommendationAction, session: AsyncSession = Depends(get_session)):
    if payload.action == "approve":
        ok = _rc.approve(rec_id)
    elif payload.action == "dismiss":
        ok = _rc.dismiss(rec_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {payload.action}")
    if not ok:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    db_ok = await _update_rec_status(session, rec_id, payload.action + "d" if payload.action == "approve" else payload.action)
    return {"status": "ok", "rec_id": rec_id, "action": payload.action, "db_updated": db_ok}


# ── Daily Engineering Brief ──────────────────────────────────────────────────


@router.get("/brief")
async def daily_brief(session: AsyncSession = Depends(get_session)):
    from backend.learning.experience_store import ExperienceStore

    trends = _at.get_summary()
    rec_stats = _rc.get_stats()
    exp_store = ExperienceStore()
    recent_experiences = [e.to_dict() for e in exp_store.list_all(limit=5)]

    repo_result = await session.execute(
        select(RepositoryRecord).where(RepositoryRecord.is_active == True)
    )
    repos = list(repo_result.scalars().all())

    brief = {
        "health_score": trends.get("health_score", 0),
        "improving": trends.get("improving", 0),
        "declining": trends.get("declining", 0),
        "stable": trends.get("stable", 0),
        "metrics": trends.get("metrics", []),
        "recommendations": {
            "total": rec_stats.get("total", 0),
            "open": rec_stats.get("open", 0),
            "approved": rec_stats.get("approved", 0),
            "dismissed": rec_stats.get("dismissed", 0),
        },
        "repositories": [
            {"id": r.id, "full_name": r.full_name, "language": r.language_summary.get("primary_language", "")}
            for r in repos
        ],
        "recent_experiences": recent_experiences,
        "experience_count": exp_store.count(),
    }
    return brief
