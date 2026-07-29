from __future__ import annotations

import os
import tempfile

from backend.learning.evaluator import EvaluationResult, SelfEvaluator
from backend.learning.experience_store import ExperienceEntry, ExperienceStore
from backend.learning.pattern_store import Pattern, PatternStore
from backend.learning.repo_analytics import RepoAnalytics


class TestExperienceEntry:
    def test_defaults(self):
        entry = ExperienceEntry()
        assert entry.id is not None
        assert entry.execution_id == ""
        assert entry.objective == ""
        assert entry.tools_used == []
        assert entry.failures == []
        assert entry.fixes == []
        assert entry.duration_ms == 0
        assert entry.outcome == ""

    def test_full_construction(self):
        entry = ExperienceEntry(
            objective="Fix login bug",
            plan_summary="Fix auth",
            tools_used=["WriteFile", "RunPyTest"],
            failures=["test_login failed"],
            fixes=["Fixed token expiry"],
            duration_ms=5000,
            outcome="success",
            execution_id="exec-1",
            repository_id="repo-1",
        )
        assert entry.objective == "Fix login bug"
        assert "WriteFile" in entry.tools_used
        assert entry.outcome == "success"

    def test_to_dict_and_from_dict_roundtrip(self):
        entry = ExperienceEntry(
            objective="Add pagination",
            outcome="failure",
            duration_ms=3000,
            execution_id="exec-2",
        )
        data = entry.to_dict()
        restored = ExperienceEntry.from_dict(data)
        assert restored.id == entry.id
        assert restored.objective == "Add pagination"
        assert restored.outcome == "failure"
        assert restored.duration_ms == 3000
        assert restored.execution_id == "exec-2"


class TestExperienceStore:
    def test_store_and_retrieve(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ExperienceStore(directory=tmpdir)
            entry = ExperienceEntry(objective="Test task", outcome="success")
            store.store(entry)
            retrieved = store.get(entry.id)
            assert retrieved is not None
            assert retrieved.objective == "Test task"
            assert retrieved.outcome == "success"

    def test_search_similar(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ExperienceStore(directory=tmpdir)
            e1 = ExperienceEntry(objective="Add JWT authentication to API", outcome="success")
            e2 = ExperienceEntry(objective="Implement pagination for list endpoint", outcome="failure")
            store.store(e1)
            store.store(e2)
            results = store.search_similar("JWT auth", limit=5)
            assert len(results) >= 1
            assert results[0][0].objective == "Add JWT authentication to API"

    def test_list_recent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ExperienceStore(directory=tmpdir)
            e1 = ExperienceEntry(objective="Task A", outcome="success")
            e2 = ExperienceEntry(objective="Task B", outcome="failure")
            store.store(e1)
            store.store(e2)
            recent = store.list_recent(limit=10)
            assert len(recent) >= 2

    def test_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ExperienceStore(directory=tmpdir)
            assert store.count() == 0
            store.store(ExperienceEntry(objective="Test", outcome="success"))
            assert store.count() == 1

    def test_clear(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ExperienceStore(directory=tmpdir)
            store.store(ExperienceEntry(objective="Test", outcome="success"))
            assert store.count() == 1
            store.clear()
            assert store.count() == 0


class TestPattern:
    def test_defaults(self):
        p = Pattern()
        assert p.name == ""
        assert p.description == ""
        assert p.dependencies == []
        assert p.best_practices == []

    def test_full_construction(self):
        p = Pattern(
            name="JWT Auth",
            description="Token-based auth",
            category="auth",
            template_code="def auth(): pass",
            dependencies=["jose"],
            best_practices=["Rotate keys"],
            related_patterns=["CRUD"],
        )
        assert p.name == "JWT Auth"
        assert p.category == "auth"
        assert "jose" in p.dependencies

    def test_to_dict_and_from_dict_roundtrip(self):
        p = Pattern(name="Test Pattern", category="test", template_code="x = 1")
        data = p.to_dict()
        restored = Pattern.from_dict(data)
        assert restored.name == "Test Pattern"
        assert restored.category == "test"
        assert restored.template_code == "x = 1"


class TestPatternStore:
    def test_builtin_patterns_loaded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = PatternStore(directory=tmpdir)
            count = store.count()
            assert count >= 8
            jwt = store.get("JWT Authentication")
            assert jwt is not None
            assert jwt.name == "JWT Authentication"

    def test_search_patterns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = PatternStore(directory=tmpdir)
            results = store.search_patterns("jwt")
            assert len(results) >= 1
            assert "jwt" in results[0].name.lower()

    def test_list_by_category(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = PatternStore(directory=tmpdir)
            api_patterns = store.get_by_category("api")
            assert len(api_patterns) >= 2

    def test_store_custom_pattern(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = PatternStore(directory=tmpdir)
            p = Pattern(name="Custom Pattern", category="custom", template_code="custom_code")
            store.store(p)
            retrieved = store.get("Custom Pattern")
            assert retrieved is not None
            assert retrieved.template_code == "custom_code"


class TestEvaluationResult:
    def test_defaults(self):
        r = EvaluationResult()
        assert r.requirements_satisfied is True
        assert r.regressions_detected == []
        assert r.architecture_consistent is True
        assert r.refactor_needed is False
        assert r.score == 1.0
        assert r.passed is True

    def test_failed_evaluation(self):
        r = EvaluationResult(
            requirements_satisfied=False,
            regressions_detected=["Test failure"],
            architecture_consistent=False,
            refactor_needed=True,
            score=0.3,
        )
        assert r.passed is False
        assert r.score == 0.3
        assert "Test failure" in r.regressions_detected

    def test_to_dict(self):
        r = EvaluationResult(summary="All good", score=0.9)
        data = r.to_dict()
        assert data["summary"] == "All good"
        assert data["score"] == 0.9
        assert data["requirements_satisfied"] is True


class TestSelfEvaluator:
    def test_evaluate_no_ollama_no_errors(self):
        evaluator = SelfEvaluator(ollama_client=None)
        result = evaluator.evaluate(
            user_request="list files",
            tool_requests=[],
            tool_responses=[],
            errors=[],
        )
        assert result.__class__.__name__ == "coroutine"

    async def test_evaluate_with_errors(self):
        evaluator = SelfEvaluator(ollama_client=None)
        result = await evaluator.evaluate(
            user_request="add auth",
            tool_requests=[],
            tool_responses=[],
            errors=["test_login failed: AssertionError"],
        )
        assert result.regressions_detected
        assert not result.passed

    async def test_evaluate_clean(self):
        evaluator = SelfEvaluator(ollama_client=None)
        result = await evaluator.evaluate(
            user_request="read files",
            tool_requests=[],
            tool_responses=[],
            errors=[],
        )
        assert result.passed
        assert result.score >= 0.9


class TestRepoAnalytics:
    def test_defect_rate_empty(self):
        store = ExperienceStore(directory=tempfile.mkdtemp())
        analytics = RepoAnalytics(store)
        rate = analytics.defect_rate()
        assert rate == 0.0

    def test_frequently_changed_files_empty(self):
        store = ExperienceStore(directory=tempfile.mkdtemp())
        analytics = RepoAnalytics(store)
        files = analytics.frequently_changed_files()
        assert files == []

    def test_common_failure_patterns_empty(self):
        store = ExperienceStore(directory=tempfile.mkdtemp())
        analytics = RepoAnalytics(store)
        patterns = analytics.common_failure_patterns()
        assert patterns == []

    def test_avg_duration_by_outcome_empty(self):
        store = ExperienceStore(directory=tempfile.mkdtemp())
        analytics = RepoAnalytics(store)
        durations = analytics.avg_duration_by_outcome()
        assert durations == {}

    def test_tool_usage_frequency_empty(self):
        store = ExperienceStore(directory=tempfile.mkdtemp())
        analytics = RepoAnalytics(store)
        tools = analytics.tool_usage_frequency()
        assert tools == []

    def test_summary_empty(self):
        store = ExperienceStore(directory=tempfile.mkdtemp())
        analytics = RepoAnalytics(store)
        summary = analytics.summary()
        assert "error" in summary
