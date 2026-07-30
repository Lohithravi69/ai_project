from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class GitHubConnection(Base, TimestampMixin):
    __tablename__ = "github_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    token_masked: Mapped[str] = mapped_column(String(32), nullable=False)
    user_login: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    repositories: Mapped[list[RepositoryRecord]] = relationship(back_populates="connection", cascade="all, delete-orphan")


class RepositoryRecord(Base, TimestampMixin):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    connection_id: Mapped[str] = mapped_column(String(36), ForeignKey("github_connections.id", ondelete="CASCADE"), nullable=False)
    github_id: Mapped[int] = mapped_column(Integer, nullable=False)
    full_name: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    clone_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    local_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(255), default="main", nullable=False)
    language_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    framework_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    scan_status: Mapped[str] = mapped_column(String(64), default="pending", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    connection: Mapped[GitHubConnection] = relationship(back_populates="repositories")
    scans: Mapped[list[ScanRun]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    files: Mapped[list[FileRecord]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    chats: Mapped[list[ChatSession]] = relationship(back_populates="repository", cascade="all, delete-orphan")


class ScanRun(Base, TimestampMixin):
    __tablename__ = "scan_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="queued", nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    function_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    class_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    route_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)

    repository: Mapped[RepositoryRecord] = relationship(back_populates="scans")


class FileRecord(Base, TimestampMixin):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    language: Mapped[str] = mapped_column(String(128), default="unknown", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    symbols_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    repository: Mapped[RepositoryRecord] = relationship(back_populates="files")
    chunks: Mapped[list[ChunkRecord]] = relationship(back_populates="file", cascade="all, delete-orphan")


class ChunkRecord(Base, TimestampMixin):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    file_id: Mapped[str] = mapped_column(String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_id: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    file: Mapped[FileRecord] = relationship(back_populates="chunks")


class ChatSession(Base, TimestampMixin):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), default="Repository Chat", nullable=False)

    repository: Mapped[RepositoryRecord] = relationship(back_populates="chats")
    messages: Mapped[list[ChatMessage]] = relationship(back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base, TimestampMixin):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    session: Mapped[ChatSession] = relationship(back_populates="messages")


class AgentExecution(Base, TimestampMixin):
    __tablename__ = "agent_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    repository_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True)
    agent_name: Mapped[str] = mapped_column(String(255), nullable=False)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="queued", nullable=False)
    step_logs: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ActionPlanRecord(Base, TimestampMixin):
    __tablename__ = "action_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    repository_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, default="", nullable=False)
    affected_repositories_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    affected_files_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    estimated_risk: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)
    required_tools_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    rollback_strategy: Mapped[str] = mapped_column(Text, default="", nullable=False)
    approval_status: Mapped[str] = mapped_column(String(32), default="pending_approval", nullable=False)
    execution_order_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    plan_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ExecutionCheckpoint(Base, TimestampMixin):
    __tablename__ = "execution_checkpoints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    plan_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("action_plans.id", ondelete="SET NULL"), nullable=True)
    repository_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True)
    branch_name: Mapped[str] = mapped_column(String(255), nullable=False)
    git_sha: Mapped[str] = mapped_column(String(128), nullable=False)
    modified_files_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, default="", nullable=False)
    plan_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ToolInvocationLog(Base, TimestampMixin):
    __tablename__ = "tool_invocation_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    plan_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("action_plans.id", ondelete="SET NULL"), nullable=True)
    checkpoint_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("execution_checkpoints.id", ondelete="SET NULL"), nullable=True)
    repository_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    inputs_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    outputs_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    execution_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    exception_message: Mapped[str] = mapped_column(Text, default="", nullable=False)


# ── Phase 2 ORM models ──────────────────────────────────────────────────────


class EmbeddingsMeta(Base):
    __tablename__ = "embeddings_meta"

    embedding_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    chunk_id: Mapped[str] = mapped_column(String(36), ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False)
    chroma_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    dimension: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vector: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ProjectGraphNode(Base):
    __tablename__ = "project_graph_nodes"

    node_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    node_type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ProjectGraphEdge(Base):
    __tablename__ = "project_graph_edges"

    edge_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    repository_id: Mapped[str] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    from_node: Mapped[str] = mapped_column(String(36), ForeignKey("project_graph_nodes.node_id", ondelete="CASCADE"), nullable=False)
    to_node: Mapped[str] = mapped_column(String(36), ForeignKey("project_graph_nodes.node_id", ondelete="CASCADE"), nullable=False)
    edge_type: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ConversationMemory(Base):
    __tablename__ = "conversation_memory"

    memory_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    memory_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    embedding_ref: Mapped[str | None] = mapped_column(String(36), ForeignKey("embeddings_meta.embedding_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class AgentMemory(Base):
    __tablename__ = "agent_memory"

    agent_memory_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    repository_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("repositories.id"), nullable=True)
    agent_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class RetrievalLog(Base):
    __tablename__ = "retrieval_logs"

    retrieval_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    repository_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    query_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    query_meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    top_k: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ChatHistory(Base):
    __tablename__ = "chat_history"

    chat_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    repository_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    assistant_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_chunks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


# ── Phase 3 ORM models ──────────────────────────────────────────────────────


class ExecutionPlanRecord(Base):
    __tablename__ = "execution_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, default="", nullable=False)
    repository_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    affected_files_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    required_tools_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    execution_order_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    risk_score: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)
    estimated_duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rollback_strategy: Mapped[str] = mapped_column(Text, default="", nullable=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    plan_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    ai_reasoning_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    agent_trace_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    architecture_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    agent_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    pipeline_stage: Mapped[str] = mapped_column(String(64), default="plan", nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class ToolExecutionRecord(Base):
    __tablename__ = "tool_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    plan_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("execution_plans.id", ondelete="SET NULL"), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tool_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    workspace_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    execution_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    exception_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ToolRegistryRecord(Base):
    __tablename__ = "tool_registry"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    permission_level: Mapped[str] = mapped_column(String(32), default="read", nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    rollback_support: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dry_run_support: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    input_schema_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    output_schema_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class WorkspaceRecord(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    plan_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("execution_plans.id", ondelete="SET NULL"), nullable=True)
    repository_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True)
    repository_full_name: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    workspace_path: Mapped[str] = mapped_column(Text, nullable=False)
    branch_name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="created", nullable=False)
    commit_sha: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class ApprovalRequestRecord(Base):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey("execution_plans.id", ondelete="CASCADE"), nullable=False)
    diff_preview: Mapped[str] = mapped_column(Text, default="", nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    reviewer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class CheckpointRecord(Base):
    __tablename__ = "checkpoints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    plan_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("execution_plans.id", ondelete="SET NULL"), nullable=True)
    workspace_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True)
    repository_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    branch_name: Mapped[str] = mapped_column(String(255), nullable=False)
    git_sha: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    modified_files_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, default="", nullable=False)
    plan_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class RollbackHistoryRecord(Base):
    __tablename__ = "rollback_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    checkpoint_id: Mapped[str] = mapped_column(String(36), ForeignKey("checkpoints.id", ondelete="CASCADE"), nullable=False)
    plan_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    repository_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    rollback_type: Mapped[str] = mapped_column(String(32), default="git", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    restored_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    restored_git_sha: Mapped[str | None] = mapped_column(String(128), nullable=True)
    execution_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    exception_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class ExecutionLogRecord(Base, TimestampMixin):
    __tablename__ = "execution_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    plan_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    tool_execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    level: Mapped[str] = mapped_column(String(16), default="info", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


# ── Phase 5 ORM models ──────────────────────────────────────────────────────


class AutonomousTaskRecord(Base, TimestampMixin):
    __tablename__ = "autonomous_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    mode: Mapped[str] = mapped_column(String(32), default="full", nullable=False)
    repository_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    plan_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    result_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    repair_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_repair_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    progress_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    progress_entries: Mapped[list[TaskProgressRecord]] = relationship(back_populates="task", cascade="all, delete-orphan")
    repairs: Mapped[list[RepairAttemptRecord]] = relationship(back_populates="task", cascade="all, delete-orphan")
    analyses: Mapped[list[FailureAnalysisRecord]] = relationship(back_populates="task", cascade="all, delete-orphan")
    reports: Mapped[list[ExecutionReportRecord]] = relationship(back_populates="task", cascade="all, delete-orphan")


class TaskProgressRecord(Base, TimestampMixin):
    __tablename__ = "task_progress"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("autonomous_tasks.id"), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    stage: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    score: Mapped[float | None] = mapped_column(Integer, nullable=True)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    task: Mapped[AutonomousTaskRecord] = relationship(back_populates="progress_entries")


class FailureAnalysisRecord(Base, TimestampMixin):
    __tablename__ = "failure_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("autonomous_tasks.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    recovery_strategy: Mapped[str] = mapped_column(Text, default="", nullable=False)
    recovery_command_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    task: Mapped[AutonomousTaskRecord] = relationship(back_populates="analyses")


class RepairAttemptRecord(Base, TimestampMixin):
    __tablename__ = "repair_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("autonomous_tasks.id"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    changes_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    score_before: Mapped[float | None] = mapped_column(Integer, nullable=True)
    score_after: Mapped[float | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    task: Mapped[AutonomousTaskRecord] = relationship(back_populates="repairs")


class EngineeringExperienceRecord(Base, TimestampMixin):
    __tablename__ = "engineering_experiences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="general", nullable=False)
    keywords_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    solution_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    success_rate: Mapped[float] = mapped_column(Integer, default=0.0, nullable=False)
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class EngineeringPatternRecord(Base, TimestampMixin):
    __tablename__ = "engineering_patterns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="architecture", nullable=False)
    applicability_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    implementation_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    consequences_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    related_patterns_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class ExecutionReportRecord(Base, TimestampMixin):
    __tablename__ = "execution_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("autonomous_tasks.id"), nullable=True)
    plan_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    report_type: Mapped[str] = mapped_column(String(64), default="engineering", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sections_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    recommendations_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    task: Mapped[AutonomousTaskRecord] = relationship(back_populates="reports")


class ArchitectureRecommendationRecord(Base, TimestampMixin):
    __tablename__ = "architecture_recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("autonomous_tasks.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="design", nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    affected_files_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    tradeoffs_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    confidence: Mapped[float] = mapped_column(Integer, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="proposed", nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


# ── Phase 6 Evolution Engine models ────────────────────────────────────────


class RecommendationRecord(Base, TimestampMixin):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)
    priority: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    effort_estimate: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)
    affected_files_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    repository_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class DebtItemRecord(Base, TimestampMixin):
    __tablename__ = "debt_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    line_start: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    line_end: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)
    metric_name: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    metric_value: Mapped[float] = mapped_column(Integer, default=0.0, nullable=False)
    suggestion: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    repository_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class VersionPlanRecord(Base, TimestampMixin):
    __tablename__ = "version_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    current_version: Mapped[str] = mapped_column(String(32), nullable=False)
    suggested_version: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    reasons_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    changes_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    risks_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    estimated_effort: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="proposed", nullable=False)
    repository_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class AnalyticsTrendRecord(Base, TimestampMixin):
    __tablename__ = "analytics_trends"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    metric_name: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_value: Mapped[float] = mapped_column(Integer, default=0.0, nullable=False)
    metric_unit: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    direction: Mapped[str] = mapped_column(String(16), default="stable", nullable=False)
    change_percent: Mapped[float] = mapped_column(Integer, default=0.0, nullable=False)
    repository_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
