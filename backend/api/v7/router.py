from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import RecommendationRecord, DebtItemRecord, VersionPlanRecord, AnalyticsTrendRecord
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


# ── Technical Debt Analyzer ─────────────────────────────────────────────────


@router.post("/analyze/debt")
async def analyze_debt(payload: AnalyzeFilesRequest):
    items = _debt.analyze_files(payload.files)
    summary = _debt.generate_summary(items)
    return {"items": [i.to_dict() for i in items], "summary": summary}


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
async def analyze_full(payload: FullAnalysisRequest):
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

    _rc.add_from_debt([i.to_dict() for i in debt_items])
    _rc.add_from_arch([c.to_dict() for c in arch_changes])
    _rc.add_from_deps(all_dep_recs)
    _rc.add_from_perf([f.to_dict() for f in perf_findings])
    _rc.add_from_security([f.to_dict() for f in sec_findings])
    recommendations = _rc.get_by_priority()

    at.record("debt_score", debt_summary.get("total_score", 0), "points")
    at.record("perf_score", perf_summary.get("score", 10), "points")
    at.record("sec_risk", sec_summary.get("risk_score", 0), "points")

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
async def plan_version(payload: VersionPlanRequest):
    plan = _vp.generate_plan(
        current_version=payload.current_version,
        debt_summary=payload.debt_summary or None,
        arch_changes=payload.arch_changes or None,
        dep_recs=payload.dep_recs or None,
        perf_findings=payload.perf_findings or None,
        sec_findings=payload.sec_findings or None,
    )
    return plan.to_dict()


# ── Repository Analytics ────────────────────────────────────────────────────


@router.get("/analytics/trends")
async def get_trends(metric: str | None = Query(None)):
    if metric:
        return {"metric": metric, "data": _at.get_trend(metric)}
    return _at.get_summary()


@router.post("/analytics/record")
async def record_metric(metric_name: str = Query(...), value: float = Query(...), unit: str = Query(default=""), repository_id: str = Query(default="")):
    snapshot = _at.record(metric_name, value, unit)
    return snapshot.to_dict()


# ── Recommendation Center ────────────────────────────────────────────────────


@router.get("/recommendations")
async def list_recommendations(status: str | None = Query(None), grouped: bool = Query(False)):
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
async def recommendation_action(rec_id: str, payload: RecommendationAction):
    if payload.action == "approve":
        ok = _rc.approve(rec_id)
    elif payload.action == "dismiss":
        ok = _rc.dismiss(rec_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {payload.action}")
    if not ok:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return {"status": "ok", "rec_id": rec_id, "action": payload.action}
