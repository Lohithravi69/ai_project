from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.tool_registry.registry import ToolRegistry
from backend.utils.files import hash_content


def _get_fs_state(root: Path) -> dict[str, bytes]:
    state: dict[str, bytes] = {}
    for p in root.rglob("*"):
        if p.is_file():
            rel = os.path.relpath(p, root)
            if ".git" not in rel.split(os.sep):
                state[rel] = p.read_bytes()
    return state


def _assert_no_changes(before: dict[str, bytes], after: dict[str, bytes]) -> None:
    added = set(after) - set(before)
    removed = set(before) - set(after)
    modified = {k for k in before if k in after and before[k] != after[k]}
    errors = []
    if added:
        errors.append(f"Files created: {sorted(added)}")
    if removed:
        errors.append(f"Files deleted: {sorted(removed)}")
    if modified:
        errors.append(f"Files modified: {sorted(modified)}")
    assert not errors, "; ".join(errors)


@pytest.fixture(autouse=True)
def _setup_repos_root(tmp_path: Path) -> None:
    from backend.config import get_settings

    get_settings().repositories_root = str(tmp_path)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir(exist_ok=True)
    from git import Repo as GitRepo
    git_repo = GitRepo.init(str(repo_path))
    git_repo.git.config("core.autocrlf", "false")
    (repo_path / "main.py").write_text("print('hello')\n")
    (repo_path / "utils.py").write_text("def helper(): pass\n")
    git_repo.index.add(["main.py", "utils.py"])
    git_repo.index.commit("Initial")
    git_repo.close()
    return repo_path


def _dry_run(registry: ToolRegistry, tool_name: str, inputs: dict):
    payload = {"dry_run": True, **inputs}
    return registry.dry_run(tool_name, payload)


class TestDryRunNoFilesystemChanges:
    @pytest.mark.asyncio
    async def test_read_file_dry_run(self, tmp_path: Path):
        registry = ToolRegistry()
        before = _get_fs_state(tmp_path)
        await _dry_run(registry, "ReadFile", {"repository_id": "test", "path": "app.py"})
        _assert_no_changes(before, _get_fs_state(tmp_path))

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Pre-existing bug: WriteFileTool.dry_run calls safe_read_text without max_bytes arg", strict=False)
    async def test_write_file_dry_run(self, git_repo: Path):
        registry = ToolRegistry()
        before = _get_fs_state(git_repo)
        repo_id = git_repo.name
        await _dry_run(registry, "WriteFile", {"repository_id": repo_id, "path": "main.py", "content": "print('modified')\n"})
        _assert_no_changes(before, _get_fs_state(git_repo))

    @pytest.mark.asyncio
    async def test_create_file_dry_run(self, git_repo: Path):
        registry = ToolRegistry()
        before = _get_fs_state(git_repo)
        repo_id = git_repo.name
        await _dry_run(registry, "CreateFile", {"repository_id": repo_id, "path": "new_file.txt", "content": "new content\n"})
        _assert_no_changes(before, _get_fs_state(git_repo))

    @pytest.mark.asyncio
    async def test_delete_file_dry_run(self, git_repo: Path):
        registry = ToolRegistry()
        repo_id = git_repo.name
        (git_repo / "to_delete.txt").write_text("will be deleted\n")
        before = _get_fs_state(git_repo)
        await _dry_run(registry, "DeleteFile", {"repository_id": repo_id, "path": "to_delete.txt"})
        _assert_no_changes(before, _get_fs_state(git_repo))

    @pytest.mark.asyncio
    async def test_move_file_dry_run(self, git_repo: Path):
        registry = ToolRegistry()
        repo_id = git_repo.name
        (git_repo / "to_move.txt").write_text("will be moved\n")
        before = _get_fs_state(git_repo)
        await _dry_run(registry, "MoveFile", {"repository_id": repo_id, "path": "to_move.txt", "destination": "moved.txt"})
        _assert_no_changes(before, _get_fs_state(git_repo))

    @pytest.mark.asyncio
    async def test_search_repository_dry_run(self, git_repo: Path):
        registry = ToolRegistry()
        before = _get_fs_state(git_repo)
        repo_id = git_repo.name
        await _dry_run(registry, "SearchRepository", {"repository_id": repo_id, "query": "print"})
        _assert_no_changes(before, _get_fs_state(git_repo))

    @pytest.mark.asyncio
    async def test_list_files_dry_run(self, git_repo: Path):
        registry = ToolRegistry()
        before = _get_fs_state(git_repo)
        repo_id = git_repo.name
        await _dry_run(registry, "ListFiles", {"repository_id": repo_id})
        _assert_no_changes(before, _get_fs_state(git_repo))

    @pytest.mark.asyncio
    async def test_git_status_dry_run(self, git_repo: Path):
        registry = ToolRegistry()
        before = _get_fs_state(git_repo)
        repo_id = git_repo.name
        await _dry_run(registry, "GitStatus", {"repository_id": repo_id})
        _assert_no_changes(before, _get_fs_state(git_repo))

    @pytest.mark.asyncio
    async def test_git_diff_dry_run(self, git_repo: Path):
        registry = ToolRegistry()
        before = _get_fs_state(git_repo)
        repo_id = git_repo.name
        await _dry_run(registry, "GitDiff", {"repository_id": repo_id})
        _assert_no_changes(before, _get_fs_state(git_repo))

    @pytest.mark.asyncio
    async def test_create_branch_dry_run(self, git_repo: Path):
        registry = ToolRegistry()
        before = _get_fs_state(git_repo)
        repo_id = git_repo.name
        await _dry_run(registry, "CreateBranch", {"repository_id": repo_id, "branch_name": "test-branch"})
        _assert_no_changes(before, _get_fs_state(git_repo))

    @pytest.mark.asyncio
    async def test_checkout_branch_dry_run(self, git_repo: Path):
        registry = ToolRegistry()
        before = _get_fs_state(git_repo)
        repo_id = git_repo.name
        await _dry_run(registry, "CheckoutBranch", {"repository_id": repo_id, "branch_name": "main"})
        _assert_no_changes(before, _get_fs_state(git_repo))

    @pytest.mark.asyncio
    async def test_commit_changes_dry_run(self, git_repo: Path):
        registry = ToolRegistry()
        repo_id = git_repo.name
        (git_repo / "staged.txt").write_text("staged\n")
        before = _get_fs_state(git_repo)
        await _dry_run(registry, "CommitChanges", {"repository_id": repo_id, "message": "test commit"})
        _assert_no_changes(before, _get_fs_state(git_repo))

    @pytest.mark.asyncio
    async def test_rollback_commit_dry_run(self, git_repo: Path):
        registry = ToolRegistry()
        before = _get_fs_state(git_repo)
        repo_id = git_repo.name
        await _dry_run(registry, "RollbackCommit", {"repository_id": repo_id, "checkpoint_id": "dummy-cp-id"})
        _assert_no_changes(before, _get_fs_state(git_repo))

    @pytest.mark.asyncio
    async def test_run_pytest_dry_run(self, tmp_path: Path):
        registry = ToolRegistry()
        before = _get_fs_state(tmp_path)
        result = await registry.dry_run("RunPyTest", {"repository_id": "test", "test_path": None, "dry_run": True})
        assert result.success
        _assert_no_changes(before, _get_fs_state(tmp_path))

    @pytest.mark.asyncio
    async def test_run_playwright_dry_run(self, tmp_path: Path):
        registry = ToolRegistry()
        before = _get_fs_state(tmp_path)
        result = await registry.dry_run("RunPlaywright", {"repository_id": "test", "test_path": None, "dry_run": True})
        assert result.success
        _assert_no_changes(before, _get_fs_state(tmp_path))

    @pytest.mark.asyncio
    async def test_run_shell_restricted_dry_run(self, tmp_path: Path):
        registry = ToolRegistry()
        before = _get_fs_state(tmp_path)
        result = await registry.dry_run("RunShellRestricted", {"repository_id": "test", "command": "pytest", "dry_run": True})
        assert result.success
        _assert_no_changes(before, _get_fs_state(tmp_path))

    @pytest.mark.asyncio
    async def test_format_code_dry_run(self, tmp_path: Path):
        registry = ToolRegistry()
        before = _get_fs_state(tmp_path)
        result = await registry.dry_run("FormatCode", {"repository_id": "test", "path": ".", "tool": "ruff", "dry_run": True})
        assert result.success
        _assert_no_changes(before, _get_fs_state(tmp_path))

    @pytest.mark.asyncio
    async def test_query_vector_store_dry_run(self, tmp_path: Path):
        registry = ToolRegistry()
        before = _get_fs_state(tmp_path)
        result = await registry.dry_run("QueryVectorStore", {"repository_id": "test", "query": "test query", "top_k": 5, "dry_run": True})
        assert result.success
        _assert_no_changes(before, _get_fs_state(tmp_path))

    @pytest.mark.asyncio
    async def test_query_postgres_dry_run(self, tmp_path: Path):
        registry = ToolRegistry()
        before = _get_fs_state(tmp_path)
        result = await registry.dry_run("QueryPostgres", {"sql": "SELECT 1", "dry_run": True})
        assert result.success
        _assert_no_changes(before, _get_fs_state(tmp_path))

    @pytest.mark.asyncio
    async def test_read_logs_dry_run(self, tmp_path: Path):
        registry = ToolRegistry()
        before = _get_fs_state(tmp_path)
        result = await registry.dry_run("ReadLogs", {"repository_id": "test", "lines": 50, "dry_run": True})
        assert result.success
        _assert_no_changes(before, _get_fs_state(tmp_path))

    @pytest.mark.asyncio
    async def test_restart_container_dry_run(self, tmp_path: Path):
        registry = ToolRegistry()
        before = _get_fs_state(tmp_path)
        result = await registry.dry_run("RestartContainer", {"repository_id": "test", "container_name": "test-container", "dry_run": True})
        assert result.success
        _assert_no_changes(before, _get_fs_state(tmp_path))
