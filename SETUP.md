# AI Development Operating System - Setup & Usage Guide

## Overview

**AI Dev OS** is a local repository intelligence engine built with Phase 2 enhancements. It combines advanced code chunking, knowledge graphs, embeddings, and RAG (Retrieval-Augmented Generation) to understand codebases deeply and enable intelligent queries.

## Prerequisites

- **Docker & Docker Compose** (for running services)
- **Python 3.13+** (for local development)
- **Node.js 18+** (for Next.js frontend)
- **Git** (for repository operations)

Optional:
- **Ollama** (for local LLM inference; or use external API)
- **PostgreSQL 16** (local; optional if using Docker)

## Quick Start (Docker)

### 1. Clone and setup

```bash
cd c:\ai_project
cp backend/.env.example backend/.env
```

### 2. Start all services

```bash
docker-compose up -d
```

This starts:
- PostgreSQL (port 5432) — database
- Redis (port 6379) — short-term memory & task queue
- Chroma (port 8001) — vector store
- Ollama (port 11434) — LLM & embedding service
- Backend (port 8000) — FastAPI
- Celery Worker — async task processing
- Celery Beat — scheduled tasks
- Frontend (port 3000) — Next.js UI

### 3. Pull Ollama models

In a separate terminal, pull the required models:

```bash
ollama pull nomic-embed-text
ollama pull qwen2.5-coder
```

### 4. Access the system

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

## Local Development (No Docker)

### 1. Set up Python environment

```bash
cd c:\ai_project
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

### 2. Set up database

```bash
# Start PostgreSQL (ensure it's running)
psql -U postgres -f infrastructure/postgres/init.sql
```

### 3. Set environment variables

```powershell
$env:DATABASE_URL = "postgresql://ai_dev_os:ai_dev_os_password@localhost:5432/ai_dev_os"
$env:REDIS_URL = "redis://localhost:6379/0"
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:CHROMA_PERSIST_DIRECTORY = "./vector_store/chroma"
```

### 4. Start services

**Terminal 1 — Backend:**
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Celery Worker:**
```bash
cd backend
celery -A execution.celery_app:celery_app worker --loglevel=info
```

**Terminal 3 — Frontend:**
```bash
cd frontend
npm run dev
```

## Architecture

### Backend Services

- **FastAPI** — REST API
- **SQLAlchemy (async)** — ORM with PostgreSQL
- **ChromaDB** — Vector store for embeddings
- **Ollama** — LLM inference (Qwen2.5-Coder) + embeddings (nomic-embed-text)
- **Celery + Redis** — Async task queue
- **PyGithub + GitPython** — GitHub integration
- **Tree-sitter** — Code parsing (optional)

### Frontend

- **Next.js (App Router)** — React UI framework
- **TypeScript** — Type safety
- **Tailwind CSS** — Styling
- **Fetch API** — Backend communication

### Database Schema

Key tables:

| Table | Purpose |
|-------|---------|
| `github_connections` | GitHub account tokens & metadata |
| `repositories` | Cloned repositories & metadata |
| `files` | Repository files with symbol counts |
| `chunks` | Code chunks (chunking strategy) |
| `embeddings_meta` | Embedding metadata & Chroma IDs |
| `project_graph_nodes` | Knowledge graph nodes (file, function, class, etc.) |
| `project_graph_edges` | Knowledge graph edges (imports, defines, etc.) |
| `conversation_memory` | Long-term memory (embedded & stored) |
| `agent_memory` | Agent-specific memory |
| `chat_sessions` | Chat session tracking |
| `chat_messages` | Chat message history |

## API Endpoints (v2)

### Semantic Search

**POST** `/api/v2/search/semantic`

```json
{
  "query": "how is authentication handled?",
  "repository_id": "repo-uuid",
  "top_k": 8
}
```

Returns chunks ranked by semantic similarity.

### RAG Chat

**POST** `/api/v2/chat/rag`

```json
{
  "query": "explain the data flow in this repository",
  "repository_id": "repo-uuid",
  "session_id": "optional-session-uuid",
  "top_k": 8
}
```

Retrieves relevant chunks and generates an answer via LLM.

### Repository Analysis

**POST** `/api/v2/repository/analyze`

```json
{
  "repository_id": "repo-uuid",
  "repo_root": "optional-path"
}
```

Builds a knowledge graph. Returns node and edge counts.

### Project Health

**POST** `/api/v2/project/health`

```json
{
  "repository_id": "repo-uuid",
  "repo_root": "optional-path"
}
```

Analyzes large files, duplicates, missing docs, dead code candidates.

### Project Graph

**POST** `/api/v2/repository/graph`

```json
{
  "repository_id": "repo-uuid",
  "limit": 1000
}
```

Returns all graph nodes and edges.

### Conversation Memory

**POST** `/api/v2/memory/conversation`

```json
{
  "repository_id": "repo-uuid",
  "session_id": "optional-session-uuid",
  "limit": 100
}
```

Retrieves long-term memory entries.

## Frontend Pages

- **Dashboard** — Home; repository overview
- **Semantic Search** — Query code by semantic meaning
- **Project Health** — Codebase metrics & issues
- **RAG Chat** — Multi-turn conversation about codebase
- **Repository Knowledge** — Knowledge graph metadata
- **Project Graph** — Nodes & edges visualization
- **Memory Viewer** — Browse conversation memory

## Workflow

### 1. Connect GitHub

- Use frontend or POST `/api/github/connect` with account name & token.
- Saves connection & syncs repositories.

### 2. Clone Repository

- POST `/api/repositories/{repo_id}/sync` with GitHub token to clone/pull repo locally.

### 3. Scan Repository

- POST `/api/repositories/{repo_id}/scan` to trigger Celery job.
- Parses files, extracts symbols, builds knowledge graph.
- Chunks code and embeds chunks via Ollama.
- Stores vectors in Chroma and metadata in DB.

### 4. Query Repository

- **Semantic Search:** Search by meaning
- **RAG Chat:** Ask complex questions
- **Project Health:** Get metrics
- **Knowledge Graph:** Explore structure

## Troubleshooting

### Port conflicts

If ports are in use, update `docker-compose.yml` or use different host ports.

### Ollama models not found

Ensure models are pulled:
```bash
ollama pull nomic-embed-text
ollama pull qwen2.5-coder
```

### Database connection error

Check:
```bash
psql -U ai_dev_os -h localhost -d ai_dev_os
```

### Frontend can't reach backend

Check `NEXT_PUBLIC_BACKEND_URL` environment variable:
```bash
# In frontend/.env.local or docker-compose.yml
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

### Celery tasks not running

Check Redis:
```bash
redis-cli ping
# Should return "PONG"
```

## Performance Tips

### For large repositories (>100k LOC)

- Increase chunk size and overlap in `backend/services/chunking.py`
- Batch process files in `backend/services/embeddings_pipeline.py`
- Use Celery worker scaling: `docker-compose up -d --scale celery-worker=3`

### Vector search optimization

- Increase `top_k` limit for more context
- Use filters on metadata (language, file type)
- Monitor Chroma memory usage

## Next Steps

- [ ] Add Alembic migrations for schema versioning
- [ ] Write comprehensive unit & integration tests
- [ ] Set up CI/CD (GitHub Actions, GitLab CI)
- [ ] Performance benchmarking for large repos
- [ ] Multi-language support improvements
- [ ] Custom embedding models

## Support & Contributing

For issues, feature requests, or questions:
1. Check this documentation first
2. Review API logs: `./logs/backend.log`
3. Check Celery logs: `docker logs ai-dev-os-celery`
4. Review database schema: `infrastructure/postgres/init.sql`

---

**Happy coding with AI Dev OS! 🚀**
