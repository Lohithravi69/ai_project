from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GitHubConnectionCreate(BaseModel):
    account_name: str = Field(min_length=1, max_length=255)
    token: str = Field(min_length=1)


class GitHubConnectionRead(BaseModel):
    id: str
    account_name: str
    user_login: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class GitHubSyncRequest(BaseModel):
    connection_id: str
    token: str


class GitHubSyncResponse(BaseModel):
    repositories: list["RepositoryRead"] = Field(default_factory=list)


class RepositoryCreate(BaseModel):
    connection_id: str
    full_name: str
    clone_url: str
    default_branch: str = "main"


class RepositoryRead(BaseModel):
    id: str
    connection_id: str
    full_name: str
    clone_url: str
    local_path: str
    default_branch: str
    language_summary: dict[str, Any] = Field(default_factory=dict)
    framework_summary: dict[str, Any] = Field(default_factory=dict)
    scan_status: str
    summary: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ScanRequest(BaseModel):
    repository_id: str


class ScanResponse(BaseModel):
    task_id: str
    repository_id: str
    status: str


class FileSummaryRead(BaseModel):
    id: str
    repository_id: str
    path: str
    language: str
    summary: str
    symbols_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ProjectSummaryRead(BaseModel):
    repository_id: str
    repository_name: str
    summary: str
    language_summary: dict[str, Any] = Field(default_factory=dict)
    framework_summary: dict[str, Any] = Field(default_factory=dict)
    file_count: int
    function_count: int
    class_count: int
    route_count: int


class ChatRequest(BaseModel):
    repository_id: str
    question: str = Field(min_length=1)
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: list[dict[str, Any]] = Field(default_factory=list)


class RetrievalRequest(BaseModel):
    repository_id: str
    query: str
    top_k: int = 5


class RetrievalHit(BaseModel):
    id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    score: float


class RetrievalResponse(BaseModel):
    repository_id: str
    query: str
    results: list[RetrievalHit] = Field(default_factory=list)


class RepositoryFilesResponse(BaseModel):
    repository_id: str
    files: list[FileSummaryRead] = Field(default_factory=list)


class ToolSpecRead(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    permission_level: str
    timeout_seconds: int
    rollback_support: bool
    dry_run_support: bool


class ToolInvocationRequest(BaseModel):
    tool_name: str = Field(min_length=1)
    repository_id: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    plan_id: str | None = None
    dry_run: bool = True
    reasoning: str = Field(default="")


class ToolInvocationResponse(BaseModel):
    tool_name: str
    dry_run: bool
    success: bool
    execution_ms: int
    result: dict[str, Any] = Field(default_factory=dict)
    affected_files: list[str] = Field(default_factory=list)
    diff_preview: str | None = None
    estimated_impact: str = ""
    risks: list[str] = Field(default_factory=list)
    checkpoint_id: str | None = None
    requires_approval: bool = False
    exception_message: str = ""
    log_id: str | None = None


class PlanStepRead(BaseModel):
    order: int
    title: str
    description: str
    tools: list[str] = Field(default_factory=list)
    dry_run: bool = True


class ActionPlanCreateRequest(BaseModel):
    objective: str = Field(min_length=1)
    request_text: str = Field(min_length=1)
    repository_ids: list[str] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    reasoning: str = Field(default="")


class ActionPlanRead(BaseModel):
    plan_id: str
    objective: str
    reasoning: str
    affected_repositories: list[dict[str, Any]] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    estimated_risk: str
    required_tools: list[str] = Field(default_factory=list)
    rollback_strategy: str
    approval_status: str
    execution_order: list[PlanStepRead] = Field(default_factory=list)


class PlanApprovalRequest(BaseModel):
    approved: bool = True
    reviewer: str = Field(default="")


class CheckpointRead(BaseModel):
    checkpoint_id: str
    plan_id: str | None = None
    repository_id: str | None = None
    branch_name: str
    git_sha: str
    modified_files: list[str] = Field(default_factory=list)
    reasoning: str = ""
    plan: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class RollbackCommitInput(BaseModel):
    checkpoint_id: str
    dry_run: bool = False


class RollbackRequest(BaseModel):
    checkpoint_id: str
    dry_run: bool = False


class RollbackResponse(BaseModel):
    checkpoint_id: str
    repository_id: str | None = None
    success: bool
    dry_run: bool
    restored_branch: str | None = None
    restored_git_sha: str | None = None
    summary: str = ""
    execution_ms: int = 0
    exception_message: str = ""


GitHubSyncResponse.model_rebuild()
RepositoryFilesResponse.model_rebuild()
