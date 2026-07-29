# Observability

## What is recorded

- Agent executions in PostgreSQL via `agent_executions`
- Retrieval traces in PostgreSQL via `retrieval_logs`
- RAG debug payloads returned from `/api/v2/chat/rag`
- System dependency status from `/api/v2/system/health`

## Backend endpoints

- `GET /api/v2/observability/agents`
- `GET /api/v2/observability/retrieval`
- `GET /api/v2/observability/usage`
- `GET /api/v2/system/health`

## Frontend dashboards

- `/agent-timeline`
- `/retrieval-debugger`
- `/token-context`
- `/system-health`

## Troubleshooting

- If agent history is empty, confirm the backend has a reachable PostgreSQL database.
- If Celery queue data is empty, confirm the worker container is running.
- If system health reports degraded status, inspect Ollama, Redis, ChromaDB, and PostgreSQL connectivity first.
