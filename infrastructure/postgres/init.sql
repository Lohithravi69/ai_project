CREATE TABLE IF NOT EXISTS github_connections (
    id VARCHAR(36) PRIMARY KEY,
    account_name VARCHAR(255) NOT NULL,
    token_masked VARCHAR(32) NOT NULL,
    user_login VARCHAR(255),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS repositories (
    id VARCHAR(36) PRIMARY KEY,
    connection_id VARCHAR(36) NOT NULL REFERENCES github_connections(id) ON DELETE CASCADE,
    github_id INTEGER NOT NULL,
    full_name VARCHAR(512) NOT NULL UNIQUE,
    clone_url VARCHAR(1024) NOT NULL,
    local_path VARCHAR(1024) NOT NULL,
    default_branch VARCHAR(255) NOT NULL DEFAULT 'main',
    language_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    framework_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    scan_status VARCHAR(64) NOT NULL DEFAULT 'pending',
    summary TEXT NOT NULL DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scan_runs (
    id VARCHAR(36) PRIMARY KEY,
    repository_id VARCHAR(36) NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    status VARCHAR(64) NOT NULL DEFAULT 'queued',
    file_count INTEGER NOT NULL DEFAULT 0,
    function_count INTEGER NOT NULL DEFAULT 0,
    class_count INTEGER NOT NULL DEFAULT 0,
    route_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS files (
    id VARCHAR(36) PRIMARY KEY,
    repository_id VARCHAR(36) NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    path VARCHAR(1024) NOT NULL,
    language VARCHAR(128) NOT NULL DEFAULT 'unknown',
    content_hash VARCHAR(128) NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    symbols_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(repository_id, path)
);

CREATE TABLE IF NOT EXISTS chunks (
    id VARCHAR(36) PRIMARY KEY,
    file_id VARCHAR(36) NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    repository_id VARCHAR(36) NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding_id VARCHAR(255) NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id VARCHAR(36) PRIMARY KEY,
    repository_id VARCHAR(36) NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL DEFAULT 'Repository Chat',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Embeddings metadata (Chroma stores vectors on disk; we keep metadata here)
CREATE TABLE IF NOT EXISTS embeddings_meta (
    embedding_id VARCHAR(36) PRIMARY KEY,
    chunk_id VARCHAR(36) NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    chroma_id TEXT,
    model_name TEXT,
    dimension INTEGER,
    vector JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Project graph nodes and edges
CREATE TABLE IF NOT EXISTS project_graph_nodes (
    node_id VARCHAR(36) PRIMARY KEY,
    repository_id VARCHAR(36) NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    node_type VARCHAR(64) NOT NULL,
    name TEXT NOT NULL,
    canonical_path TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project_graph_edges (
    edge_id VARCHAR(36) PRIMARY KEY,
    repository_id VARCHAR(36) NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    from_node VARCHAR(36) NOT NULL REFERENCES project_graph_nodes(node_id) ON DELETE CASCADE,
    to_node VARCHAR(36) NOT NULL REFERENCES project_graph_nodes(node_id) ON DELETE CASCADE,
    edge_type VARCHAR(64) NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Conversation and agent memory
CREATE TABLE IF NOT EXISTS conversation_memory (
    memory_id VARCHAR(36) PRIMARY KEY,
    session_id TEXT,
    memory_type VARCHAR(32) NOT NULL,
    title TEXT,
    content TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding_ref VARCHAR(36) REFERENCES embeddings_meta(embedding_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_memory (
    agent_memory_id VARCHAR(36) PRIMARY KEY,
    repository_id VARCHAR(36) REFERENCES repositories(id),
    agent_name TEXT,
    artifact_type TEXT,
    content JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS retrieval_logs (
    retrieval_id VARCHAR(36) PRIMARY KEY,
    repository_id VARCHAR(36),
    query_text TEXT,
    query_meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    results JSONB NOT NULL DEFAULT '[]'::jsonb,
    top_k INTEGER,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Optional chat_history audit table (aggregated view of conversations)
CREATE TABLE IF NOT EXISTS chat_history (
    chat_id VARCHAR(36) PRIMARY KEY,
    session_id TEXT,
    repository_id VARCHAR(36),
    user_message TEXT,
    assistant_message TEXT,
    context_chunks JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_executions (
    id VARCHAR(36) PRIMARY KEY,
    repository_id VARCHAR(36) REFERENCES repositories(id) ON DELETE SET NULL,
    agent_name VARCHAR(255) NOT NULL,
    task_name VARCHAR(255) NOT NULL,
    status VARCHAR(64) NOT NULL DEFAULT 'queued',
    step_logs JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT NOT NULL DEFAULT '',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS action_plans (
    id VARCHAR(36) PRIMARY KEY,
    repository_id VARCHAR(36) REFERENCES repositories(id) ON DELETE SET NULL,
    objective TEXT NOT NULL,
    reasoning TEXT NOT NULL DEFAULT '',
    affected_repositories_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    affected_files_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    estimated_risk VARCHAR(32) NOT NULL DEFAULT 'medium',
    required_tools_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    rollback_strategy TEXT NOT NULL DEFAULT '',
    approval_status VARCHAR(32) NOT NULL DEFAULT 'pending_approval',
    execution_order_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    plan_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS execution_checkpoints (
    id VARCHAR(36) PRIMARY KEY,
    plan_id VARCHAR(36) REFERENCES action_plans(id) ON DELETE SET NULL,
    repository_id VARCHAR(36) REFERENCES repositories(id) ON DELETE SET NULL,
    branch_name VARCHAR(255) NOT NULL,
    git_sha VARCHAR(128) NOT NULL,
    modified_files_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    reasoning TEXT NOT NULL DEFAULT '',
    plan_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tool_invocation_logs (
    id VARCHAR(36) PRIMARY KEY,
    plan_id VARCHAR(36) REFERENCES action_plans(id) ON DELETE SET NULL,
    checkpoint_id VARCHAR(36) REFERENCES execution_checkpoints(id) ON DELETE SET NULL,
    repository_id VARCHAR(36) REFERENCES repositories(id) ON DELETE SET NULL,
    tool_name VARCHAR(255) NOT NULL,
    inputs_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    outputs_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    dry_run BOOLEAN NOT NULL DEFAULT TRUE,
    success BOOLEAN NOT NULL DEFAULT FALSE,
    execution_ms INTEGER NOT NULL DEFAULT 0,
    exception_message TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
