# Phase 2 Brainstorm Plan (RAG + Project Memory + Semantic Search)

## Information Gathered
- Current system (Phase 1) structure:
  - FastAPI app with `/api` router (see `backend/api/router.py`). Existing endpoints: GitHub connect/sync, repository sync, scan, summary, chat, retrieval/search.
  - Celery task `scan_repository_task` in `backend/execution/celery_app.py` calls `ScannerService.scan_repository`.
  - `ScannerService` (in `backend/services/scanner_service.py`) currently:
    - Uses `TreeSitterParser` but mostly regex-based extraction.
    - Builds file summaries and a project summary.
    - Chunks files using `backend/utils/files.py::chunk_text` (fixed-length likely).
    - Embeds chunks via Ollama embedding endpoint.
    - Stores vectors in a single Chroma collection `repository_chunks` with `repository_id` metadata filter.
    - Persists chunks in Postgres via existing `ChunkRecord` model.
  - Chroma integration uses `upsert_chunks` and `search` (cosine-ish via distances -> score = 1 - distance).
  - Database schema today includes: repositories, files, chunks, chat_sessions, chat_messages, scan_runs, github_connections.
  - There is no explicit “project knowledge graph”, no unified multi-repo memory, and no semantic search beyond vector similarity over raw chunk text.

- What must change to meet Phase 2:
  - Replace fixed-length chunking with intelligent, typed chunks (function/class/route/api/config/dependency).
  - Add new DB tables/schemas for:
    - rich chunk metadata fields
    - project knowledge graph
    - conversation memory and agent memory
    - retrieval logs and chat history (beyond current chat_messages)
  - Implement incremental re-indexing: embed only changed files/chunks.
  - Build dependency mapping and architecture graph generation (`project_map.json`).
  - Add multi-repository memory abstraction and allow cross-repo query.
  - Add RAG pipeline improvements: query expansion/reranking/context ranking + conversation memory retrieval.
  - Implement Project Explainer Agent: architecture/API/workflow/data-flow/DB design summaries + diagrams.
  - Implement Project Health Analysis: unused/dead code, duplicate code, missing documentation, large files, circular dependencies.
  - Build frontend memory dashboard pages to visualize graph and retrieval/search.

## Edit Plan (High-Level)
### Phase 2 will be implemented in these slices
1. **Schema & model upgrades**
   - Extend `backend/database/models.py` with new models:
     - `RepositoryKnowledgeGraph` (or `ProjectGraphEdge/Node`)
     - `AgentMemory` and `ConversationMemory`
     - `RetrievalLog`
     - `ChatHistory` (or enrich existing chat tables)
   - Extend `ChunkRecord` or create a new `TypedChunkRecord` with required fields:
     - chunk_id, file_path, repository_id, language, framework
     - function_name, class_name, summary, source_code, dependencies
     - plus metadata_json for compatibility.

2. **Advanced code chunking system**
   - Implement new chunker module:
     - `backend/parsers/chunking.py` (or similar)
   - Chunk extraction based on file language using:
     - existing regex extraction (stopgap)
     - tree-sitter AST when available
   - Generate chunk types and hierarchical chunking (e.g., function chunks nested within class chunks).

3. **Embedding pipeline & incremental re-index**
   - Update `ScannerService` into a pipeline:
     - detect changed files using `content_hash`
     - only re-chunk/re-embed changed files
     - batch embed with `ollama.embed_texts` but with chunk limits
     - async execution using Celery tasks per repository or per file
   - Update Chroma integration to store typed-chunk metadata and stable ids.

4. **Project knowledge graph**
   - Build import/function-call/class inheritance/route mapping/dependency mapping.
   - Persist in Postgres graph tables.
   - Emit `project_map.json` to repository storage and/or DB.

5. **Conversation memory system**
   - Create `backend/services/memory_service.py` with:
     - short_term_memory: per-session rolling window
     - long_term_memory: per-user/project persistent memories
   - Add retrieval-before-every-chat behavior inside chat/RAG pipeline.

6. **Semantic search engine**
   - Add new endpoint `/api/search/semantic`.
   - Retrieval outputs ranked:
     - relevant files
     - relevant functions
     - relevant classes
     - relevant typed chunks
   - Implement reranking using embedding similarity + metadata boosting.

7. **RAG chat engine**
   - Replace simplistic `chat_service` retrieval with:
     - query embedding
     - vector search with typed chunk metadata filtering
     - cross-repo retrieval mode
     - context ranking step
     - prompt construction using architecture hints + conversation memory

8. **Project explainer agent + health analysis**
   - Implement `backend/agents/project_explainer.py`
   - Implement `backend/agents/project_health.py`
   - Expose endpoints:
     - `/api/repository/analyze`
     - `/api/project/health`

9. **Frontend dashboard**
   - Add pages/components to visualize:
     - repository knowledge
     - project graph
     - memory viewer
     - semantic search
     - architecture viewer
     - RAG chat interface

### Dependent Files to edit (initial)
- `backend/database/models.py`
- `backend/models/schemas.py`
- `backend/api/router.py`
- `backend/services/scanner_service.py`
- `backend/services/chat_service.py`
- `backend/embeddings/chroma_service.py`
- `backend/embeddings/ollama_client.py` (batching improvements)
- `backend/parsers/tree_sitter_parser.py`
- Add: `backend/parsers/chunking.py`
- Add: `backend/services/memory_service.py`
- Add: `backend/agents/project_explainer.py`
- Add: `backend/agents/project_health.py`
- Frontend:
  - `frontend/app/*` pages for dashboard routes
  - components for graph/search/memory

## Database Design Proposal (summary)
- Create tables:
  - `conversation_memory`: user_id?, session_id, category (goals/chats/code_requests/bug_fixes), content, embedding(optional), created_at
  - `agent_memory`: agent_id, project_id, key, value/json, created_at/updated_at
  - `retrieval_logs`: query, repository_id(s), hit_ids, scores, model/embedding config, duration, created_at
  - `chat_history`: session_id, message_id, role/content, token counts
  - `project_graph_nodes` + `project_graph_edges`
  - `typed_chunks`: chunk_id(pk), repository_id, file_path, language, framework, chunk_type, function_name, class_name, summary, source_code, dependencies(json)

## Followup Steps
- After plan approval:
  1. Create `TODO.md` update to track Phase 2 steps.
  2. Implement DB schema updates and generate migration strategy.
  3. Implement chunker + update scanner pipeline.
  4. Implement knowledge graph builder + project_map.json.
  5. Implement memory_service and integrate into chat.
  6. Implement semantic search endpoint.
  7. Implement project explainer + health endpoints.
  8. Add frontend pages.
  9. Run lint/tests + manual integration checks.

<ask_followup_question>
Confirm that we should proceed with this Phase 2 implementation order: (1) DB/schema, (2) typed chunking + embedding pipeline incremental updates, (3) knowledge graph + project_map.json, (4) memory_service + integrate into RAG chat, (5) semantic search engine, (6) explainer + health analysis, (7) frontend dashboard.
</ask_followup_question>

