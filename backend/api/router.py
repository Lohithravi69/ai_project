from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database.models import FileRecord, GitHubConnection, RepositoryRecord
from backend.database.session import get_session
from backend.embeddings.chroma_service import ChromaService
from backend.embeddings.ollama_client import OllamaClient
from backend.github.service import GitHubService
from backend.models.schemas import (
    ChatRequest,
    ChatResponse,
    GitHubConnectionCreate,
    GitHubConnectionRead,
    GitHubSyncRequest,
    GitHubSyncResponse,
    FileSummaryRead,
    ProjectSummaryRead,
    RepositoryRead,
    RepositoryFilesResponse,
    RetrievalRequest,
    RetrievalResponse,
    ScanResponse,
)
from backend.execution.celery_app import scan_repository_task
from backend.services.chat_service import ChatService
from backend.services.repository_service import RepositoryService

router = APIRouter(prefix="/api")


def _ollama_client() -> OllamaClient:
    settings = get_settings()
    return OllamaClient(settings.ollama_base_url, settings.ollama_chat_model, settings.ollama_embed_model)


def _chroma_service() -> ChromaService:
    return ChromaService(get_settings().chroma_persist_directory)


@router.post("/github/connect", response_model=GitHubConnectionRead)
async def connect_github(payload: GitHubConnectionCreate, session: AsyncSession = Depends(get_session)):
    service = GitHubService(session)
    try:
        connection = await service.connect_account(payload.account_name, payload.token)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GitHubConnectionRead(
        id=connection.id,
        account_name=connection.account_name,
        user_login=connection.user_login,
        metadata_json=connection.metadata_json,
        created_at=connection.created_at,
    )


@router.post("/github/sync", response_model=GitHubSyncResponse)
async def sync_github_repositories(payload: GitHubSyncRequest, session: AsyncSession = Depends(get_session)):
    service = GitHubService(session)
    connection = await session.get(GitHubConnection, payload.connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="GitHub connection not found")
    repositories = await service.sync_repositories(payload.connection_id, payload.token)
    return GitHubSyncResponse(
        repositories=[
            RepositoryRead(
                id=repository.id,
                connection_id=repository.connection_id,
                full_name=repository.full_name,
                clone_url=repository.clone_url,
                local_path=repository.local_path,
                default_branch=repository.default_branch,
                language_summary=repository.language_summary,
                framework_summary=repository.framework_summary,
                scan_status=repository.scan_status,
                summary=repository.summary,
                is_active=repository.is_active,
                created_at=repository.created_at,
                updated_at=repository.updated_at,
            )
            for repository in repositories
        ]
    )


@router.get("/repositories", response_model=list[RepositoryRead])
async def list_repositories(session: AsyncSession = Depends(get_session)):
    service = RepositoryService(session)
    repositories = await service.list_repositories()
    return [
        RepositoryRead(
            id=repository.id,
            connection_id=repository.connection_id,
            full_name=repository.full_name,
            clone_url=repository.clone_url,
            local_path=repository.local_path,
            default_branch=repository.default_branch,
            language_summary=repository.language_summary,
            framework_summary=repository.framework_summary,
            scan_status=repository.scan_status,
            summary=repository.summary,
            is_active=repository.is_active,
            created_at=repository.created_at,
            updated_at=repository.updated_at,
        )
        for repository in repositories
    ]


@router.post("/repositories/{repository_id}/sync", response_model=RepositoryRead)
async def sync_repository(
    repository_id: str,
    token: str = Body(...),
    session: AsyncSession = Depends(get_session),
):
    """Sync (clone or pull) a repository.

    Notes:
    - Using `Body(...)` makes sure FastAPI reads `token` from the request body,
      avoiding common 422 errors when clients send JSON.
    """

    service = RepositoryService(session)
    try:
        repository = await service.clone_or_sync_repository(repository_id, token)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RepositoryRead(
        id=repository.id,
        connection_id=repository.connection_id,
        full_name=repository.full_name,
        clone_url=repository.clone_url,
        local_path=repository.local_path,
        default_branch=repository.default_branch,
        language_summary=repository.language_summary,
        framework_summary=repository.framework_summary,
        scan_status=repository.scan_status,
        summary=repository.summary,
        is_active=repository.is_active,
        created_at=repository.created_at,
        updated_at=repository.updated_at,
    )



@router.post("/repositories/{repository_id}/scan", response_model=ScanResponse)
async def scan_repository(repository_id: str):
    task = scan_repository_task.delay(repository_id)
    return ScanResponse(task_id=task.id, repository_id=repository_id, status="queued")


@router.get("/repositories/{repository_id}/summary", response_model=ProjectSummaryRead)
async def get_repository_summary(repository_id: str, session: AsyncSession = Depends(get_session)):
    repository = await session.get(RepositoryRecord, repository_id)
    if not repository:
        raise HTTPException(status_code=404, detail="Repository not found")
    result = await session.execute(select(FileRecord).where(FileRecord.repository_id == repository_id))
    files = list(result.scalars().all())
    file_count = len(files)
    function_count = sum(len(file.symbols_json.get("functions", [])) for file in files)
    class_count = sum(len(file.symbols_json.get("classes", [])) for file in files)
    route_count = sum(len(file.symbols_json.get("routes", [])) for file in files)
    return ProjectSummaryRead(
        repository_id=repository.id,
        repository_name=repository.full_name,
        summary=repository.summary,
        language_summary=repository.language_summary,
        framework_summary=repository.framework_summary,
        file_count=file_count,
        function_count=function_count,
        class_count=class_count,
        route_count=route_count,
    )


@router.get("/repositories/{repository_id}/files", response_model=RepositoryFilesResponse)
async def list_repository_files(repository_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(FileRecord).where(FileRecord.repository_id == repository_id).order_by(FileRecord.path.asc()))
    files = list(result.scalars().all())
    return RepositoryFilesResponse(
        repository_id=repository_id,
        files=[
            FileSummaryRead(
                id=file.id,
                repository_id=file.repository_id,
                path=file.path,
                language=file.language,
                summary=file.summary,
                symbols_json=file.symbols_json,
                created_at=file.created_at,
                updated_at=file.updated_at,
            )
            for file in files
        ],
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, session: AsyncSession = Depends(get_session)):
    service = ChatService(session, _ollama_client(), _chroma_service())
    try:
        answer, session_id, sources = await service.answer(payload.repository_id, payload.question, payload.session_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ChatResponse(session_id=session_id, answer=answer, sources=sources)


@router.post("/retrieval/search", response_model=RetrievalResponse)
async def retrieval_search(payload: RetrievalRequest):
    ollama = _ollama_client()
    chroma = _chroma_service()
    query_embedding = await ollama.embed_text(payload.query)
    results = chroma.search(query_embedding=query_embedding, repository_id=payload.repository_id, top_k=payload.top_k)
    return RetrievalResponse(repository_id=payload.repository_id, query=payload.query, results=results)
