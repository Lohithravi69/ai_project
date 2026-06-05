from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


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
