from __future__ import annotations

from backend.evolution.debt_analyzer import TechnicalDebtAnalyzer, DebtItem
from backend.evolution.architecture_engine import ArchitectureEvolutionEngine, ArchChange
from backend.evolution.dependency_intel import DependencyIntelligence, DepRecommendation
from backend.evolution.performance_advisor import PerformanceAdvisor, PerfFinding
from backend.evolution.security_advisor import SecurityAdvisor, SecurityFinding
from backend.evolution.version_planner import VersionEvolutionPlanner, VersionPlan
from backend.evolution.analytics_tracker import AnalyticsTracker, TrendSnapshot
from backend.evolution.recommendation_center import RecommendationCenter, PrioritizedRecommendation

__all__ = [
    "TechnicalDebtAnalyzer", "DebtItem",
    "ArchitectureEvolutionEngine", "ArchChange",
    "DependencyIntelligence", "DepRecommendation",
    "PerformanceAdvisor", "PerfFinding",
    "SecurityAdvisor", "SecurityFinding",
    "VersionEvolutionPlanner", "VersionPlan",
    "AnalyticsTracker", "TrendSnapshot",
    "RecommendationCenter", "PrioritizedRecommendation",
]
