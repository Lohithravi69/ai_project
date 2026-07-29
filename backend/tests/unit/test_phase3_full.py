from __future__ import annotations

from pathlib import Path

import pytest

from backend.execution.diff_engine import DiffEngine
from backend.tool_registry.registry import ToolRegistry


class TestToolRegistry:
    def test_registry_is_singleton(self):
        r1 = ToolRegistry()
        r2 = ToolRegistry()
        assert r1 is r2

    def test_registry_exposes_all_21_tools(self):
        registry = ToolRegistry()
        names = registry.list_tool_names()
        assert len(names) == 21
        required = {
            "ReadFile", "WriteFile", "CreateFile", "DeleteFile", "MoveFile",
            "SearchRepository", "ListFiles", "GitStatus", "GitDiff",
            "CreateBranch", "CheckoutBranch", "CommitChanges", "RollbackCommit",
            "RunPyTest", "RunPlaywright", "RunShellRestricted", "FormatCode",
            "QueryVectorStore", "QueryPostgres", "ReadLogs", "RestartContainer",
        }
        assert required.issubset(names)

    def test_each_tool_has_required_fields(self):
        registry = ToolRegistry()
        for spec in registry.list_tools():
            assert spec.name
            assert spec.description is not None
            assert spec.version
            assert spec.permission_level in ("read", "write")
            assert spec.timeout_seconds > 0
            assert isinstance(spec.dry_run_support, bool)
            assert isinstance(spec.rollback_support, bool)

    def test_get_tool_by_name(self):
        registry = ToolRegistry()
        tool = registry.get_tool("ReadFile")
        assert tool.spec.name == "ReadFile"
        assert tool.spec.permission_level == "read"

    def test_get_unknown_tool_raises(self):
        registry = ToolRegistry()
        with pytest.raises(ValueError, match="Unknown tool"):
            registry.get_tool("NonExistentTool")

    @pytest.mark.asyncio
    async def test_read_file_dry_run(self):
        registry = ToolRegistry()
        result = await registry.dry_run("ReadFile", {"repository_id": "test", "path": "app.py", "dry_run": True})
        assert result.success
        assert result.result["would_read"] is True
        assert result.affected_files == ["app.py"]

    @pytest.mark.asyncio
    async def test_write_file_dry_run_returns_diff(self):
        registry = ToolRegistry()
        result = await registry.dry_run("WriteFile", {"repository_id": "test", "path": "app.py", "content": "print('new')\n", "dry_run": True})
        assert result.success
        assert result.diff_preview is not None

    @pytest.mark.asyncio
    async def test_create_file_dry_run(self):
        registry = ToolRegistry()
        result = await registry.dry_run("CreateFile", {"repository_id": "test", "path": "new.py", "content": "", "dry_run": True})
        assert result.success
        assert result.estimated_impact == "creates one file"

    @pytest.mark.asyncio
    async def test_delete_file_dry_run(self):
        registry = ToolRegistry()
        result = await registry.dry_run("DeleteFile", {"repository_id": "test", "path": "old.py", "dry_run": True})
        assert result.success is False

    @pytest.mark.asyncio
    async def test_search_repository_dry_run(self):
        registry = ToolRegistry()
        result = await registry.dry_run("SearchRepository", {"repository_id": "test", "query": "print", "dry_run": True})
        assert result.success

    @pytest.mark.asyncio
    async def test_git_tools_dry_run(self):
        registry = ToolRegistry()
        for name in ["GitStatus", "GitDiff", "CreateBranch", "CheckoutBranch", "CommitChanges"]:
            result = await registry.dry_run(name, {"repository_id": "test", "dry_run": True, **({"branch_name": "test-branch"} if name in ("CreateBranch", "CheckoutBranch") else {}), **({"message": "test"} if name == "CommitChanges" else {})})
            assert result.success, f"{name} dry run failed"

    @pytest.mark.asyncio
    async def test_shell_tools_dry_run(self):
        registry = ToolRegistry()
        for name in ["RunPyTest", "RunPlaywright", "RunShellRestricted", "FormatCode"]:
            result = await registry.dry_run(name, {"repository_id": "test", "dry_run": True, **({"command": "pytest"} if name == "RunShellRestricted" else {})})
            assert result.success, f"{name} dry run failed"

    @pytest.mark.asyncio
    async def test_query_tools_dry_run(self):
        registry = ToolRegistry()
        result = await registry.dry_run("QueryVectorStore", {"repository_id": "test", "query": "test", "top_k": 5, "dry_run": True})
        assert result.success

        result = await registry.dry_run("QueryPostgres", {"sql": "SELECT 1", "dry_run": True})
        assert result.success

    @pytest.mark.asyncio
    async def test_logs_container_tools_dry_run(self):
        registry = ToolRegistry()
        result = await registry.dry_run("ReadLogs", {"repository_id": "test", "lines": 50, "dry_run": True})
        assert result.success

        result = await registry.dry_run("RestartContainer", {"repository_id": "test", "container_name": "test", "dry_run": True})
        assert result.success


class TestDiffEngine:
    def test_unified_diff(self):
        engine = DiffEngine()
        old = "line1\nline2\nline3\n"
        new = "line1\nline2_modified\nline3\nline4\n"
        diff = engine.unified(old, new, "test.py")
        assert "line2" in diff
        assert "line4" in diff

    def test_side_by_side_diff(self):
        engine = DiffEngine()
        old = "a\nb\nc\n"
        new = "a\nb_modified\nc\nd\n"
        sbs = engine.side_by_side(old, new)
        assert "OLD" in sbs
        assert "NEW" in sbs

    def test_file_summary_counts_lines(self):
        engine = DiffEngine()
        old = "a\nb\nc\n"
        new = "a\nb\nc\nd\ne\n"
        summary = engine.file_summary(old, new, "test.py")
        assert summary["added_lines"] == 2
        assert summary["deleted_lines"] == 0

    def test_file_summary_detects_functions(self):
        engine = DiffEngine()
        old = "def foo():\n    pass\n"
        new = "def foo():\n    return 1\n\ndef bar():\n    pass\n"
        summary = engine.file_summary(old, new, "test.py")
        assert "foo" in summary["modified_functions"]

    def test_compare_strings(self):
        engine = DiffEngine()
        old = "x = 1\n"
        new = "x = 2\n"
        result = engine.compare_strings(old, new, "test.py")
        assert "unified" in result
        assert "side_by_side" in result
        assert "estimated_impact" in result


class TestSecurity:
    def test_permission_validator_file_size(self):
        from backend.execution.security import PermissionValidator

        v = PermissionValidator()
        with pytest.raises(ValueError, match="exceeds maximum"):
            v.validate_file_size(20_000_000)

    def test_permission_validator_timeout(self):
        from backend.execution.security import PermissionValidator

        v = PermissionValidator()
        with pytest.raises(ValueError, match="exceeds maximum"):
            v.validate_timeout(1200)

    def test_permission_validator_sql_read_only(self):
        from backend.execution.security import PermissionValidator

        v = PermissionValidator()
        v.validate_sql_read_only("SELECT * FROM users")
        with pytest.raises(ValueError, match="Only read-only"):
            v.validate_sql_read_only("DELETE FROM users")

    def test_permission_validator_workspace_path(self):
        from backend.execution.security import PermissionValidator

        v = PermissionValidator()
        with pytest.raises(PermissionError, match="outside allowed root"):
            v.validate_workspace_path("/etc/passwd", "/safe/root")


class TestValidationEngine:
    def test_validation_result(self):
        from backend.execution.validation_engine import ValidationResult

        r = ValidationResult(success=True, validator="pytest", output="passed", duration_ms=100)
        assert r.success
        assert r.validator == "pytest"
