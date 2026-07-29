# AI Dev OS Architecture

## High-Level System

```mermaid
flowchart TD
  U[Developer] --> F[Next.js Frontend]
  F --> B[FastAPI Backend]
  B --> P[(PostgreSQL)]
  B --> R[(Redis)]
  B --> C[(ChromaDB)]
  B --> O[Ollama]
  B --> G[GitHub / Local Git Repositories]
  B --> W[Celery Workers]
  W --> B
  W --> C
  W --> P
```

## Repository Sync and Incremental Indexing

```mermaid
flowchart LR
  A[Git Pull / File Change Monitor] --> B[Hash Changed Files]
  B --> C[Delete Old Chunks + Graph Nodes]
  C --> D[Parse Changed Files]
  D --> E[Create New Chunks]
  E --> F[Generate Embeddings]
  F --> G[Upsert ChromaDB]
  E --> H[Update PostgreSQL Metadata]
  D --> I[Update Project Graph]
```

## RAG Request Flow

```mermaid
sequenceDiagram
  participant User
  participant Frontend
  participant FastAPI
  participant Retriever
  participant Chroma
  participant Ollama
  participant PostgreSQL

  User->>Frontend: Ask question
  Frontend->>FastAPI: POST /api/v2/chat/rag
  FastAPI->>Retriever: retrieve(query)
  Retriever->>Chroma: semantic search
  Retriever->>PostgreSQL: short-term memory lookup
  FastAPI->>Ollama: generate answer
  FastAPI->>PostgreSQL: log retrieval + execution data
  FastAPI-->>Frontend: answer + debug trace
```

## Folder Guide

- `backend/` - FastAPI app, services, and background tasks
- `frontend/` - Next.js app router UI and dashboards
- `docker/` - Container build definitions
- `infrastructure/` - Database bootstrap and deployment assets
- `scripts/` - One-command operational scripts
- `docs/` - API, architecture, and support documentation
