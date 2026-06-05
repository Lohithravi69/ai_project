# API Documentation

## Health

- `GET /health`

## GitHub

- `POST /api/github/connect`
- `POST /api/github/sync`

### `POST /api/github/connect`

Request body:

```json
{
  "account_name": "local-dev-account",
  "token": "github_pat_..."
}
```

### `POST /api/github/sync`

Request body:

```json
{
  "connection_id": "uuid",
  "token": "github_pat_..."
}
```

## Repositories

- `GET /api/repositories`
- `POST /api/repositories/{repository_id}/sync`
- `POST /api/repositories/{repository_id}/scan`
- `GET /api/repositories/{repository_id}/summary`
- `GET /api/repositories/{repository_id}/files`

## Chat

- `POST /api/chat`

### `POST /api/chat`

Request body:

```json
{
  "repository_id": "uuid",
  "question": "Explain this project",
  "session_id": null
}
```

## Retrieval

- `POST /api/retrieval/search`

### `POST /api/retrieval/search`

Request body:

```json
{
  "repository_id": "uuid",
  "query": "How does authentication work?",
  "top_k": 5
}
```

## Data Model Summary

The PostgreSQL schema contains:

- GitHub connections
- Repository metadata
- Scan runs
- File summaries
- Chunk records
- Chat sessions
- Chat messages
