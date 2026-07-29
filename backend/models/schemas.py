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


# ── Phase 3 Schemas ─────────────────────────────────────────────────────────


class ToolDefinition(BaseModel):
    id: str = ""
    name: str
    description: str = ""
    version: str = "1.0.0"
    permission_level: str = "read"
    timeout_seconds: int = 30
    rollback_support: bool = False
    dry_run_support: bool = True
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)


class ToolRunRequest(BaseModel):
    tool_name: str = Field(min_length=1)
    inputs: dict[str, Any] = Field(default_factory=dict)
    plan_id: str | None = None
    workspace_id: str | None = None
    dry_run: bool = True
    reasoning: str = Field(default="")
    execution_id: str | None = None


class ToolRunResponse(BaseModel):
    tool_name: str
    dry_run: bool
    success: bool
    execution_ms: int = 0
    result: dict[str, Any] = Field(default_factory=dict)
    affected_files: list[str] = Field(default_factory=list)
    diff_preview: str | None = None
    estimated_impact: str = ""
    risks: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    checkpoint_id: str | None = None
    workspace_id: str | None = None
    exception_message: str = ""
    execution_id: str | None = None


class AIReasoning(BaseModel):
    reasoning: str = ""
    alternatives_considered: list[str] = Field(default_factory=list)
    why_this_choice: str = ""
    confidence: float = 0.0
    expected_risks: list[str] = Field(default_factory=list)


class ExecutionPlanCreate(BaseModel):
    objective: str = Field(min_length=1)
    request_text: str = Field(min_length=1)
    repository_ids: list[str] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    reasoning: str = Field(default="")
    ai_reasoning: AIReasoning = Field(default_factory=AIReasoning)
    execution_id: str = ""


class AgentTraceEntry(BaseModel):
    agent_name: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    input_summary: str = ""
    output_summary: str = ""
    tool_calls: int = 0
    ai_reasoning: AIReasoning = Field(default_factory=AIReasoning)
    duration_ms: int = 0
    success: bool = True
    error: str = ""


class AgentRunRequest(BaseModel):
    request_text: str = Field(min_length=1)
    repository_id: str = ""
    mode: str = "full"


class AgentRunResponse(BaseModel):
    execution_id: str
    plan_id: str = ""
    status: str = "pending"
    agent_trace: list[AgentTraceEntry] = Field(default_factory=list)
    result_summary: str = ""


class AgentStatusResponse(BaseModel):
    execution_id: str
    plan_id: str | None = None
    agent_status: str = "pending"
    current_agent: str = ""
    progress: str = ""


class ExecutionPlanRead(BaseModel):
    id: str
    objective: str
    reasoning: str = ""
    repository_ids: list[str] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    execution_order: list[dict[str, Any]] = Field(default_factory=list)
    risk_score: str = "medium"
    estimated_duration_ms: int = 0
    rollback_strategy: str = ""
    approval_required: bool = True
    approval_status: str = "pending"
    plan: dict[str, Any] = Field(default_factory=dict)
    ai_reasoning: AIReasoning = Field(default_factory=AIReasoning)
    agent_trace: list[AgentTraceEntry] = Field(default_factory=list)
    architecture: dict[str, Any] = Field(default_factory=dict)
    agent_status: str = "pending"
    created_at: datetime | None = None
    updated_at: datetime | None = None
    execution_id: str | None = None


class DiffOutput(BaseModel):
    unified: str = ""
    side_by_side: str = ""
    file_summary: list[dict[str, Any]] = Field(default_factory=list)
    added_lines: int = 0
    deleted_lines: int = 0
    modified_functions: list[str] = Field(default_factory=list)
    estimated_impact: str = ""


class ApprovalRequestRead(BaseModel):
    id: str
    plan_id: str
    diff_preview: str = ""
    explanation: str = ""
    status: str = "pending"
    reviewer: str | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str = ""
    created_at: datetime | None = None
    execution_id: str | None = None


class ApprovalAction(BaseModel):
    approved: bool = True
    reviewer: str = Field(default="")
    rejection_reason: str = Field(default="")


class WorkspaceRead(BaseModel):
    id: str
    plan_id: str | None = None
    repository_id: str | None = None
    repository_full_name: str = ""
    workspace_path: str = ""
    branch_name: str = ""
    base_branch: str = ""
    status: str = "created"
    commit_sha: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    execution_id: str | None = None


class CheckpointReadV2(BaseModel):
    id: str
    plan_id: str | None = None
    workspace_id: str | None = None
    repository_id: str | None = None
    branch_name: str = ""
    git_sha: str = ""
    tool_name: str = ""
    modified_files: list[str] = Field(default_factory=list)
    reasoning: str = ""
    plan: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    execution_id: str | None = None


class RollbackRequestV2(BaseModel):
    checkpoint_id: str
    rollback_types: list[str] = Field(default_factory=lambda: ["git"])
    dry_run: bool = False


class RollbackResponseV2(BaseModel):
    checkpoint_id: str
    success: bool
    dry_run: bool
    summary: str = ""
    restored_branch: str | None = None
    restored_git_sha: str | None = None
    rollback_results: dict[str, Any] = Field(default_factory=dict)
    execution_ms: int = 0
    exception_message: str = ""
    execution_id: str | None = None


class ExecutionLogRead(BaseModel):
    id: str
    plan_id: str | None = None
    tool_execution_id: str | None = None
    level: str = "info"
    message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    execution_id: str | None = None


# ── v6 Autonomous schemas ──────────────────────────────────────────────────


class AutonomousTaskCreate(BaseModel):
    objective: str = Field(min_length=1)
    repository_id: str = ""
    mode: str = "full"
    max_repair_attempts: int = Field(default=3, ge=0, le=10)


class AutonomousTaskRead(BaseModel):
    id: str
    objective: str
    status: str = "pending"
    mode: str = "full"
    repository_id: str = ""
    plan_id: str = ""
    result_summary: str = ""
    error_message: str = ""
    repair_attempts: int = 0
    max_repair_attempts: int = 3
    progress: list[dict[str, Any]] = Field(default_factory=list)
    analyses: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    celery_task_id: str | None = None
    created_at: str = ""
    updated_at: str = ""


class AutonomousTaskList(BaseModel):
    tasks: list[AutonomousTaskRead] = Field(default_factory=list)
    total: int = 0


class AutonomousTaskAction(BaseModel):
    action: str = Field(pattern="^(pause|resume|cancel)$")


class FailureAnalysisSchema(BaseModel):
    category: str = "unknown"
    severity: str = "medium"
    summary: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    recovery_strategies: list[dict[str, Any]] = Field(default_factory=list)


class ArchitectureRecommendationSchema(BaseModel):
    title: str = ""
    category: str = "design"
    description: str = ""
    rationale: str = ""
    affected_files: list[str] = Field(default_factory=list)
    tradeoffs: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    status: str = "proposed"


class EngineeringReportSchema(BaseModel):
    title: str = ""
    report_type: str = "engineering"
    summary: str = ""
    sections: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = 0.0


class AgentScoringRequest(BaseModel):
    agent_name: str
    tool_responses: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


GitHubSyncResponse.model_rebuild()
RepositoryFilesResponse.model_rebuild()
