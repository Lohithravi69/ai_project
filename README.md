# AI Dev OS

Local-first personal AI development operating system for GitHub repository intelligence, code understanding, and repository-aware chat.

## Architecture

The system is split into three layers:

- Frontend: Next.js dashboard with Tailwind CSS and shadcn-style UI primitives.
- Backend: FastAPI service that handles GitHub integration, repository scanning, chat, retrieval, embeddings, and task orchestration.
- Infrastructure: PostgreSQL, Redis, ChromaDB, and Ollama managed through Docker.

### Runtime flow

1. A GitHub token is sent to the backend.
2. The backend stores the connection and syncs repository metadata through PyGithub.
3. Repositories are cloned or pulled locally with GitPython.
4. The scanner walks the repository, ignores generated folders, extracts symbols, and persists summaries.
5. File chunks are embedded through Ollama using `nomic-embed-text`.
6. ChromaDB stores the vectors for semantic retrieval.
7. Chat requests retrieve the best repository chunks and answer with Qwen2.5-Coder through Ollama.

## Folder Structure

- `frontend/`: Next.js dashboard
- `backend/`: FastAPI app, services, workflows, models
- `repositories/`: Local clones of GitHub repositories
- `vector_store/`: ChromaDB persistence
- `docker/`: Dockerfiles
- `infrastructure/`: database schema and infra assets
- `logs/`: application logs
- `models/`: local model artifacts and Ollama data mounts

## Prerequisites

- Docker Desktop
- Python 3.12 if you want to run the backend outside Docker
- Node.js 20 if you want to run the frontend outside Docker

## Environment Variables

Use the example files as the source of truth:

- `backend/.env.example`
- `frontend/.env.example`

## Local Run With Docker

1. Copy the example environment values into a `.env` file if you want to override defaults.
2. Start the stack:

```powershell
docker compose up --build
```

The compose stack now includes dependency health checks, automatic Ollama model bootstrap, and startup ordering for Postgres, Redis, Chroma, backend, and workers.

3. Open the dashboard at `http://localhost:3000`.
4. The backend API is available at `http://localhost:8000`.

## Local Development Without Docker

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

## API Overview

See `docs/api.md` for endpoint details.

## Execution Flow

- The frontend sends GitHub credentials and repository chat requests to the FastAPI backend.
- The backend persists metadata in PostgreSQL and chunk embeddings in ChromaDB.
- Celery workers consume scan jobs from Redis and execute the repository scan workflow.
- Ollama handles both embedding generation and local LLM chat.

## Notes

- Tree-sitter support is wired through the parser abstraction and can be enabled with a compiled language bundle supplied through `TREE_SITTER_LANGUAGE_LIBRARY`.
- The project is designed to stay local-first and avoid external SaaS dependencies.

---

## Phase 2 Features (AI Codebase Understanding Engine)

### Advanced Code Intelligence

- **Advanced Chunking:** Semantic code chunking with type detection (function, class, route, API, config, dependency, other)
- **Knowledge Graph:** File-level dependency graph with imports, definitions, and class/function relationships
- **Embedding Pipeline:** Batch embedding of chunks via Ollama with Chroma vector storage
- **Multi-tier Memory:** Short-term Redis cache + long-term PostgreSQL storage with semantic search

### RAG Chat Engine

- Context-aware chat using retriever + LLM
- Session-based conversation memory
- Automatic chunk retrieval from semantic search

### Project Analysis

- **Project Health:** Metrics on large files, duplicates, missing documentation, dead-code candidates
- **Project Explainer:** AI-generated architecture explanations
- **Semantic Search:** Query code by meaning, not keywords

### Frontend Pages

- Semantic Search interface
- RAG Chat interface
- Project Health dashboard
- Project Graph visualizer
- Memory Viewer
- Repository Knowledge explorer

### Database Schema Enhancements

- `embeddings_meta`: Embedding metadata and Chroma IDs
- `project_graph_nodes`: Knowledge graph nodes
- `project_graph_edges`: Knowledge graph edges
- `conversation_memory`: Long-term memory storage
- `agent_memory`: Agent-specific memory
- Additional chat & session tables for conversation tracking

---

## Getting Started

For comprehensive setup and usage instructions, see **[SETUP.md](SETUP.md)**.

Quick start with Docker:

```bash
docker-compose up -d
# Pull Ollama models:
ollama pull nomic-embed-text
ollama pull qwen2.5-coder
# Open http://localhost:3000
```

## Testing

Run unit and integration tests:

```bash
pytest backend/tests/ -v
```

CI/CD pipeline is configured in `.github/workflows/ci.yml`.

## Operations

- Start: `docker compose up --build`
- Stop: `scripts/shutdown.ps1`
- Reset: `scripts/reset.ps1`
- Migrate schema: `scripts/migrate.ps1`
- Backup database: `scripts/backup.ps1`
- Restore database: `scripts/restore.ps1`

The health endpoint now reports per-dependency status at `GET /api/health`.

---

**Happy coding with AI Dev OS! 🚀**
