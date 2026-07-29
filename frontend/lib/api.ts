import type { FileSummary, ProjectSummary, Repository } from './types';

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? 'http://localhost:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${backendUrl}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    cache: 'no-store',
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || response.statusText);
  }
  return response.json() as Promise<T>;
}

export async function connectGitHub(accountName: string, token: string) {
  return request<{ id: string; account_name: string }>(`/api/github/connect`, {
    method: 'POST',
    body: JSON.stringify({ account_name: accountName, token }),
  });
}

export async function syncGitHubRepositories(connectionId: string, token: string) {
  return request<{ repositories: Repository[] }>(`/api/github/sync`, {
    method: 'POST',
    body: JSON.stringify({ connection_id: connectionId, token }),
  });
}

export async function fetchRepositories() {
  return request<Repository[]>(`/api/repositories`);
}

export async function fetchRepositorySummary(repositoryId: string) {
  return request<ProjectSummary>(`/api/repositories/${repositoryId}/summary`);
}

export async function fetchRepositoryFiles(repositoryId: string) {
  const payload = await request<{ files: FileSummary[] }>(`/api/repositories/${repositoryId}/files`);
  return payload.files;
}

export async function queueScan(repositoryId: string) {
  return request<{ task_id: string; repository_id: string; status: string }>(`/api/repositories/${repositoryId}/scan`, {
    method: 'POST',
  });
}

export async function sendChat(repositoryId: string, question: string, sessionId?: string) {
  return request<{ session_id: string; answer: string; sources: Array<Record<string, unknown>> }>(`/api/chat`, {
    method: 'POST',
    body: JSON.stringify({ repository_id: repositoryId, question, session_id: sessionId ?? null }),
  });
}

export async function semanticSearch(query: string, repositoryId?: string, topK = 8) {
  return request<{ results: Array<{ id: string; content: string; metadata: Record<string, unknown>; score: number }> }>(`/api/v2/search/semantic`, {
    method: 'POST',
    body: JSON.stringify({ query, repository_id: repositoryId ?? null, top_k: topK }),
  });
}

export async function ragChat(query: string, repositoryId?: string, sessionId?: string, topK = 8) {
  return request<{ answer: string; sources: Array<Record<string, unknown>>; debug?: Record<string, unknown> }>(`/api/v2/chat/rag`, {
    method: 'POST',
    body: JSON.stringify({ query, repository_id: repositoryId ?? null, session_id: sessionId ?? null, top_k: topK }),
  });
}

export async function analyzeRepository(repositoryId: string, repoRoot?: string) {
  return request<{ nodes: number; edges: number }>(`/api/v2/repository/analyze`, {
    method: 'POST',
    body: JSON.stringify({ repository_id: repositoryId, repo_root: repoRoot ?? null }),
  });
}

export async function projectHealth(repositoryId: string, repoRoot?: string) {
  return request<{ report: Record<string, unknown> }>(`/api/v2/project/health`, {
    method: 'POST',
    body: JSON.stringify({ repository_id: repositoryId, repo_root: repoRoot ?? null }),
  });
}

export async function projectGraph(repositoryId: string, limit = 1000) {
  return request<{ nodes: Array<Record<string, any>>; edges: Array<Record<string, any>> }>(`/api/v2/repository/graph`, {
    method: 'POST',
    body: JSON.stringify({ repository_id: repositoryId, limit }),
  });
}

export async function getConversationMemory(repositoryId?: string, sessionId?: string, limit = 100) {
  return request<{ entries: Array<Record<string, any>>; total: number }>(`/api/v2/memory/conversation`, {
    method: 'POST',
    body: JSON.stringify({ repository_id: repositoryId ?? null, session_id: sessionId ?? null, limit }),
  });
}

export async function getAgentObservability() {
  return request<{ executions: Array<Record<string, any>>; task_queue: Record<string, any> }>(`/api/v2/observability/agents`);
}

export async function getRetrievalObservability() {
  return request<{ logs: Array<Record<string, any>> }>(`/api/v2/observability/retrieval`);
}

export async function getUsageObservability() {
  return request<{ total_prompt_tokens: number; total_completion_tokens: number; avg_context_size: number; avg_retrieved_chunks: number; avg_response_time_ms: number; recent_queries: number }>(`/api/v2/observability/usage`);
}

export async function getSystemHealth() {
  return request<{ status: string; dependencies: Array<Record<string, any>>; workers: Record<string, any>; resources: Record<string, any> }>(`/api/v2/system/health`);
}
