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


GitHubSyncResponse.model_rebuild()
RepositoryFilesResponse.model_rebuild()
