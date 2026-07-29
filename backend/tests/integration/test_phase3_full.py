from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database.base import Base
from backend.database.models import (
    ApprovalRequestRecord,
    CheckpointRecord,
    ExecutionPlanRecord,
    GitHubConnection,
    RepositoryRecord,
    WorkspaceRecord,
)
from backend.models.schemas import ExecutionPlanCreate, ToolRunRequest
from backend.planner.action_planner import ActionPlanner


@pytest.fixture
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    yield session_factory
    await engine.dispose()


@pytest.fixture
async def seeded_db(test_db):
    async with test_db() as session:
        connection = GitHubConnection(account_name="test-account", token_masked="***", user_login="tester")
        session.add(connection)
        await session.commit()
        await session.refresh(connection)

        yield session


@pytest.fixture
async def repo_and_session(seeded_db, tmp_path: Path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "app.py").write_text("print('hello')\n", encoding="utf-8")

    session = seeded_db
    repository = RepositoryRecord(
        connection_id=session.info.get("connection_id", ""),
        github_id=1,
        full_name="test/repo",
        clone_url="https://example.com/test/repo.git",
        local_path=str(repo_root),
        default_branch="main",
        scan_status="synced",
        summary="",
        is_active=True,
    )
    session.add(repository)
    await session.commit()
    await session.refresh(repository)

    session.info["repository"] = repository
    session.info["repo_root"] = repo_root
    yield session


@pytest.mark.asyncio
async def test_create_read_only_plan(test_db):
    async with test_db() as session:
        planner = ActionPlanner(session)
        plan = await planner.create_plan(ExecutionPlanCreate(
            objective="Read the main file",
            request_text="Show me the contents of main.py",
            affected_files=["main.py"],
        ))
        assert plan.id
        assert plan.objective == "Read the main file"
        assert plan.approval_required is False
        assert plan.approval_status == "approved"
        assert "ReadFile" in plan.required_tools


@pytest.mark.asyncio
async def test_create_modifying_plan(test_db):
    async with test_db() as session:
        planner = ActionPlanner(session)
        plan = await planner.create_plan(ExecutionPlanCreate(
            objective="Update the authentication module",
            request_text="Add a new login endpoint to auth.py",
            affected_files=["auth.py", "routes.py"],
        ))
        assert plan.id
        assert plan.approval_required is True
        assert plan.approval_status == "pending"
        assert "WriteFile" in plan.required_tools
        assert "CreateBranch" in plan.required_tools
        assert plan.risk_score in ("low", "medium", "high")


@pytest.mark.asyncio
async def test_get_plan_returns_none_for_missing(test_db):
    async with test_db() as session:
        planner = ActionPlanner(session)
        plan = await planner.get_plan("nonexistent")
        assert plan is None


@pytest.mark.asyncio
async def test_list_plans(test_db):
    async with test_db() as session:
        planner = ActionPlanner(session)
        await planner.create_plan(ExecutionPlanCreate(objective="Test", request_text="test"))
        plans = await planner.list_plans()
        assert len(plans) == 1


@pytest.mark.asyncio
async def test_approval_workflow(test_db):
    async with test_db() as session:
        from backend.approval.approval_system import ApprovalSystem

        plan = ExecutionPlanRecord(objective="Test", reasoning="test", required_tools_json=[], execution_order_json=[], plan_json={})
        session.add(plan)
        await session.commit()
        await session.refresh(plan)

        system = ApprovalSystem(session)
        request = await system.create_approval_request(plan.id, diff_preview="diff --git a/app.py b/app.py", explanation="Test change")
        assert request.status == "pending"
        assert request.plan_id == plan.id

        from backend.models.schemas import ApprovalAction

        approved = await system.approve(request.id, ApprovalAction(approved=True, reviewer="test-bot"))
        assert approved.status == "approved"
        assert approved.reviewer == "test-bot"


@pytest.mark.asyncio
async def test_rejection_workflow(test_db):
    async with test_db() as session:
        from backend.approval.approval_system import ApprovalSystem

        plan = ExecutionPlanRecord(objective="Test", reasoning="test", required_tools_json=[], execution_order_json=[], plan_json={})
        session.add(plan)
        await session.commit()
        await session.refresh(plan)

        system = ApprovalSystem(session)
        request = await system.create_approval_request(plan.id, explanation="Bad change")
        rejected = await system.reject(request.id, reason="Not needed", reviewer="bot")
        assert rejected.status == "rejected"
        assert rejected.rejection_reason == "Not needed"


@pytest.mark.asyncio
async def test_checkpoint_engine(test_db):
    async with test_db() as session:
        from backend.execution.checkpoint_engine import CheckpointEngine

        engine = CheckpointEngine(session)
        cp_id = await engine.create_checkpoint(
            repository_id="test-repo",
            tool_name="WriteFile",
            modified_files=["app.py"],
            reasoning="test checkpoint",
        )
        assert cp_id

        cp = await engine.get_checkpoint(cp_id)
        assert cp is not None
        assert cp.tool_name == "WriteFile"
        assert "app.py" in cp.modified_files_json


@pytest.mark.asyncio
async def test_checkpoint_list_and_latest(test_db):
    async with test_db() as session:
        from backend.execution.checkpoint_engine import CheckpointEngine

        plan = ExecutionPlanRecord(objective="Test", reasoning="test", required_tools_json=[], execution_order_json=[], plan_json={})
        session.add(plan)
        await session.commit()
        await session.refresh(plan)

        engine = CheckpointEngine(session)
        cp1 = await engine.create_checkpoint(plan_id=plan.id, tool_name="WriteFile", modified_files=["a.py"], reasoning="first")
        cp2 = await engine.create_checkpoint(plan_id=plan.id, tool_name="WriteFile", modified_files=["b.py"], reasoning="second")

        checkpoints = await engine.list_checkpoints(plan_id=plan.id)
        assert len(checkpoints) >= 2

        latest = await engine.get_latest_checkpoint(plan.id)
        assert latest is not None
        assert latest.id == cp2


@pytest.mark.asyncio
async def test_rollback_engine_dry_run(test_db):
    async with test_db() as session:
        from backend.execution.checkpoint_engine import CheckpointEngine
        from backend.execution.rollback_engine import RollbackEngine

        checkpoint_engine = CheckpointEngine(session)
        cp_id = await checkpoint_engine.create_checkpoint(
            repository_id="test-repo",
            tool_name="WriteFile",
            modified_files=["app.py"],
            reasoning="test checkpoint",
        )

        rollback_engine = RollbackEngine(session)
        result = await rollback_engine.rollback(cp_id, dry_run=True)
        assert result.success
        assert result.dry_run is True


@pytest.mark.asyncio
async def test_workspace_lifecycle(test_db, tmp_path: Path, monkeypatch):
    import git as git_lib

    from backend.config import get_settings

    get_settings().repositories_root = str(tmp_path / "repositories")

    clone_from_should_not_be_called = lambda *a, **kw: (_ for _ in ()).throw(AssertionError("Repo.clone_from should not be called during workspace test"))
    monkeypatch.setattr(git_lib.Repo, "clone_from", clone_from_should_not_be_called)

    async with test_db() as session:
        from backend.execution.workspace import WorkspaceManager

        connection = GitHubConnection(account_name="ws-test", token_masked="***", user_login="tester")
        session.add(connection)
        await session.commit()
        await session.refresh(connection)

        repo_path = tmp_path / "ws-test-repo"
        repo_path.mkdir(parents=True, exist_ok=True)
        from git import Repo as GitRepo
        git_repo = GitRepo.init(str(repo_path))
        git_repo.close()

        repository = RepositoryRecord(
            connection_id=connection.id,
            github_id=2,
            full_name="ws/test-repo",
            clone_url="https://example.com/ws/test-repo.git",
            local_path=str(repo_path),
            default_branch="main",
            scan_status="synced",
            summary="",
            is_active=True,
        )
        session.add(repository)
        await session.commit()
        await session.refresh(repository)

        mgr = WorkspaceManager(session)
        ws = await mgr.create_workspace(repository.id, branch_name="test-ws", base_branch="main")
        assert ws.id
        assert ws.status == "created"
        assert ws.branch_name == "test-ws"

        workspaces = await mgr.list_workspaces(repository_id=repository.id)
        assert len(workspaces) >= 1


@pytest.mark.asyncio
async def test_execution_manager_dry_run(test_db):
    async with test_db() as session:
        from backend.execution.execution_manager import ExecutionManager

        mgr = ExecutionManager(session)
        response = await mgr.run_tool(ToolRunRequest(
            tool_name="ReadFile",
            inputs={"repository_id": "test", "path": "main.py", "dry_run": True},
            dry_run=True,
        ))
        assert response.tool_name == "ReadFile"
        assert response.dry_run is True
        assert response.success
        assert response.result.get("would_read") is True


@pytest.mark.asyncio
async def test_execution_manager_unknown_tool(test_db):
    async with test_db() as session:
        from backend.execution.execution_manager import ExecutionManager
        mgr = ExecutionManager(session)
        from backend.models.schemas import ToolRunRequest
        response = await mgr.run_tool(ToolRunRequest(
            tool_name="NonExistent",
            inputs={},
            dry_run=True,
        ))
        assert response.success is False


# ── Rollback Validation Tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rollback_validate_byte_equality(test_db, tmp_path: Path):
    repo_path = tmp_path / "rollback_eq"
    repo_path.mkdir()
    from git import Repo as GitRepo
    git_repo = GitRepo.init(str(repo_path))
    git_repo.git.config("core.autocrlf", "false")

    original_content = b"hello world\nthis is a test\nline 3\n"
    (repo_path / "test.txt").write_bytes(original_content)
    git_repo.index.add(["test.txt"])
    git_repo.index.commit("Initial commit")

    async with test_db() as session:
        connection = GitHubConnection(account_name="rb-eq", token_masked="***", user_login="tester")
        session.add(connection)
        await session.commit()
        await session.refresh(connection)

        repository = RepositoryRecord(
            connection_id=connection.id,
            github_id=1001,
            full_name="test/rollback-eq",
            clone_url="",
            local_path=str(repo_path),
            default_branch="main",
            scan_status="synced",
            summary="",
            is_active=True,
        )
        session.add(repository)
        await session.commit()
        await session.refresh(repository)

        from backend.execution.checkpoint_engine import CheckpointEngine
        checkpoint_engine = CheckpointEngine(session)
        cp_id = await checkpoint_engine.create_checkpoint(
            repository_id=repository.id,
            repo_path=str(repo_path),
            tool_name="WriteFile",
            modified_files=["test.txt"],
            reasoning="pre-modification checkpoint",
        )

        modified_content = b"modified content\n"
        (repo_path / "test.txt").write_bytes(modified_content)
        git_repo.index.add(["test.txt"])
        git_repo.index.commit("Modify file")

        from backend.execution.rollback_engine import RollbackEngine
        rollback_engine = RollbackEngine(session)
        result = await rollback_engine.rollback(cp_id, dry_run=False)
        assert result.success, f"Rollback failed: {result.exception_message}"

        restored = (repo_path / "test.txt").read_bytes()
        assert restored == original_content, f"Expected {original_content!r}, got {restored!r}"


@pytest.mark.asyncio
async def test_rollback_validate_file_deletion(test_db, tmp_path: Path):
    repo_path = tmp_path / "rollback_del"
    repo_path.mkdir()
    from git import Repo as GitRepo
    git_repo = GitRepo.init(str(repo_path))
    git_repo.git.config("core.autocrlf", "false")

    original_content = b"file to be deleted\n"
    (repo_path / "delete_me.txt").write_bytes(original_content)
    git_repo.index.add(["delete_me.txt"])
    git_repo.index.commit("Initial commit")

    async with test_db() as session:
        connection = GitHubConnection(account_name="rb-del", token_masked="***", user_login="tester")
        session.add(connection)
        await session.commit()
        await session.refresh(connection)

        repository = RepositoryRecord(
            connection_id=connection.id,
            github_id=1002,
            full_name="test/rollback-del",
            clone_url="",
            local_path=str(repo_path),
            default_branch="main",
            scan_status="synced",
            summary="",
            is_active=True,
        )
        session.add(repository)
        await session.commit()
        await session.refresh(repository)

        from backend.execution.checkpoint_engine import CheckpointEngine
        checkpoint_engine = CheckpointEngine(session)
        cp_id = await checkpoint_engine.create_checkpoint(
            repository_id=repository.id,
            repo_path=str(repo_path),
            tool_name="DeleteFile",
            modified_files=["delete_me.txt"],
            reasoning="pre-deletion checkpoint",
        )

        (repo_path / "delete_me.txt").unlink()
        git_repo.index.remove(["delete_me.txt"])
        git_repo.index.commit("Delete file")

        assert not (repo_path / "delete_me.txt").exists()

        from backend.execution.rollback_engine import RollbackEngine
        rollback_engine = RollbackEngine(session)
        result = await rollback_engine.rollback(cp_id, dry_run=False)
        assert result.success, f"Rollback failed: {result.exception_message}"

        assert (repo_path / "delete_me.txt").exists(), "File was not restored after rollback"
        restored = (repo_path / "delete_me.txt").read_bytes()
        assert restored == original_content, f"Expected {original_content!r}, got {restored!r}"


@pytest.mark.asyncio
async def test_rollback_validate_file_rename(test_db, tmp_path: Path):
    repo_path = tmp_path / "rollback_ren"
    repo_path.mkdir()
    from git import Repo as GitRepo
    git_repo = GitRepo.init(str(repo_path))
    git_repo.git.config("core.autocrlf", "false")

    original_content = b"file to be renamed\n"
    (repo_path / "original_name.txt").write_bytes(original_content)
    git_repo.index.add(["original_name.txt"])
    git_repo.index.commit("Initial commit")

    async with test_db() as session:
        connection = GitHubConnection(account_name="rb-ren", token_masked="***", user_login="tester")
        session.add(connection)
        await session.commit()
        await session.refresh(connection)

        repository = RepositoryRecord(
            connection_id=connection.id,
            github_id=1003,
            full_name="test/rollback-ren",
            clone_url="",
            local_path=str(repo_path),
            default_branch="main",
            scan_status="synced",
            summary="",
            is_active=True,
        )
        session.add(repository)
        await session.commit()
        await session.refresh(repository)

        from backend.execution.checkpoint_engine import CheckpointEngine
        checkpoint_engine = CheckpointEngine(session)
        cp_id = await checkpoint_engine.create_checkpoint(
            repository_id=repository.id,
            repo_path=str(repo_path),
            tool_name="MoveFile",
            modified_files=["original_name.txt"],
            reasoning="pre-rename checkpoint",
        )

        (repo_path / "original_name.txt").rename(repo_path / "renamed_file.txt")
        git_repo.index.add(["renamed_file.txt"])
        git_repo.index.remove(["original_name.txt"])
        git_repo.index.commit("Rename file")

        assert not (repo_path / "original_name.txt").exists()
        assert (repo_path / "renamed_file.txt").exists()

        from backend.execution.rollback_engine import RollbackEngine
        rollback_engine = RollbackEngine(session)
        result = await rollback_engine.rollback(cp_id, dry_run=False)
        assert result.success, f"Rollback failed: {result.exception_message}"

        assert (repo_path / "original_name.txt").exists(), "Original file was not restored after rollback"
        assert not (repo_path / "renamed_file.txt").exists(), "Renamed file should not exist after rollback"
        restored = (repo_path / "original_name.txt").read_bytes()
        assert restored == original_content, f"Expected {original_content!r}, got {restored!r}"


@pytest.mark.asyncio
async def test_rollback_validate_multiple_files(test_db, tmp_path: Path):
    repo_path = tmp_path / "rollback_multi"
    repo_path.mkdir()
    from git import Repo as GitRepo
    git_repo = GitRepo.init(str(repo_path))
    git_repo.git.config("core.autocrlf", "false")

    files = {
        "alpha.txt": b"alpha content\nline 2\n",
        "beta.txt": b"beta content\n",
        "gamma.txt": b"gamma\nline 2\nline 3\n",
    }
    for name, content in files.items():
        (repo_path / name).write_bytes(content)
        git_repo.index.add([name])
    git_repo.index.commit("Initial commit")

    async with test_db() as session:
        connection = GitHubConnection(account_name="rb-multi", token_masked="***", user_login="tester")
        session.add(connection)
        await session.commit()
        await session.refresh(connection)

        repository = RepositoryRecord(
            connection_id=connection.id,
            github_id=1004,
            full_name="test/rollback-multi",
            clone_url="",
            local_path=str(repo_path),
            default_branch="main",
            scan_status="synced",
            summary="",
            is_active=True,
        )
        session.add(repository)
        await session.commit()
        await session.refresh(repository)

        from backend.execution.checkpoint_engine import CheckpointEngine
        checkpoint_engine = CheckpointEngine(session)
        cp_id = await checkpoint_engine.create_checkpoint(
            repository_id=repository.id,
            repo_path=str(repo_path),
            tool_name="WriteFile",
            modified_files=list(files.keys()),
            reasoning="pre-modification checkpoint for multiple files",
        )

        (repo_path / "alpha.txt").write_text("modified alpha\n")
        (repo_path / "beta.txt").write_text("modified beta\n")
        (repo_path / "gamma.txt").write_text("modified gamma\n")
        git_repo.index.add(["alpha.txt", "beta.txt", "gamma.txt"])
        git_repo.index.commit("Modify all files")

        from backend.execution.rollback_engine import RollbackEngine
        rollback_engine = RollbackEngine(session)
        result = await rollback_engine.rollback(cp_id, dry_run=False)
        assert result.success, f"Rollback failed: {result.exception_message}"

        for name, expected_content in files.items():
            restored = (repo_path / name).read_bytes()
            assert restored == expected_content, f"{name}: expected {expected_content!r}, got {restored!r}"
