from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.health import router as health_router
from backend.api.metrics import router as metrics_router
from backend.api.router import router as api_router
from backend.api.v2.chat_rag import router as chat_rag_router
from backend.api.v2.search import router as search_router
from backend.api.v2.repository_analyze import router as analyze_router
from backend.api.v2.project_graph import router as project_graph_router
from backend.api.v2.memory import router as memory_router
from backend.api.v2.observability import router as observability_router
from backend.api.v3.phase3 import router as phase3_router
from backend.api.v4.router import router as phase4_router
from backend.config import get_settings
from backend.database.base import Base
from backend.database.session import engine
from backend.monitoring.logging import configure_logging
from backend.middleware.rate_limit import RateLimitMiddleware
from backend.services.runtime_guard import RuntimeGuard

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    guard = RuntimeGuard(settings)
    await guard.snapshot(engine)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(RateLimitMiddleware, max_requests=120, window_seconds=60)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.backend_cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(api_router)
app.include_router(chat_rag_router)
app.include_router(search_router)
app.include_router(analyze_router)
app.include_router(project_graph_router)
app.include_router(memory_router)
app.include_router(observability_router)
app.include_router(phase3_router)
app.include_router(phase4_router)
