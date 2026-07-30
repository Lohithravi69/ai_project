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

// ── Phase 3 Full (v4) API ──────────────────────────────────────────────────

export async function v4ListTools() {
  return request<Array<{
    name: string; description: string; version: string;
    permission_level: string; timeout_seconds: number;
    rollback_support: boolean; dry_run_support: boolean;
    input_schema: Record<string, any>; output_schema: Record<string, any>;
  }>>(`/api/v4/tools`);
}

export async function v4CreatePlan(payload: {
  objective: string; request_text: string;
  repository_ids?: string[]; affected_files?: string[]; reasoning?: string;
}) {
  return request<Record<string, any>>(`/api/v4/plan`, {
    method: 'POST', body: JSON.stringify(payload),
  });
}

export async function v4GetPlan(planId: string) {
  return request<Record<string, any>>(`/api/v4/plan/${planId}`);
}

export async function v4ListPlans(limit = 50) {
  return request<Array<Record<string, any>>>(`/api/v4/plans?limit=${limit}`);
}

export async function v4DryRunTool(payload: {
  tool_name: string; inputs: Record<string, any>;
  plan_id?: string; workspace_id?: string; reasoning?: string;
}) {
  return request<Record<string, any>>(`/api/v4/tools/dry-run`, {
    method: 'POST', body: JSON.stringify({ ...payload, dry_run: true }),
  });
}

export async function v4RunTool(payload: {
  tool_name: string; inputs: Record<string, any>;
  plan_id?: string; workspace_id?: string; dry_run?: boolean; reasoning?: string;
}) {
  return request<Record<string, any>>(`/api/v4/tools/run`, {
    method: 'POST', body: JSON.stringify(payload),
  });
}

export async function v4ListApprovalRequests(planId?: string, status?: string, limit = 50) {
  const params = new URLSearchParams();
  if (planId) params.set('plan_id', planId);
  if (status) params.set('status', status);
  params.set('limit', String(limit));
  return request<Array<Record<string, any>>>(`/api/v4/approval?${params}`);
}

export async function v4GetApprovalRequest(approvalId: string) {
  return request<Record<string, any>>(`/api/v4/approval/${approvalId}`);
}

export async function v4ApproveRequest(approvalId: string, reviewer = '') {
  return request<Record<string, any>>(`/api/v4/approval/approve?approval_id=${approvalId}`, {
    method: 'POST', body: JSON.stringify({ approved: true, reviewer }),
  });
}

export async function v4RejectRequest(approvalId: string, reason = '', reviewer = '') {
  return request<Record<string, any>>(`/api/v4/approval/reject?approval_id=${approvalId}`, {
    method: 'POST', body: JSON.stringify({ reason, reviewer }),
  });
}

export async function v4ListWorkspaces(repositoryId?: string, status?: string, limit = 50) {
  const params = new URLSearchParams();
  if (repositoryId) params.set('repository_id', repositoryId);
  if (status) params.set('status', status);
  params.set('limit', String(limit));
  return request<Array<Record<string, any>>>(`/api/v4/workspaces?${params}`);
}

export async function v4GetWorkspace(workspaceId: string) {
  return request<Record<string, any>>(`/api/v4/workspaces/${workspaceId}`);
}

export async function v4ListCheckpoints(planId?: string, repositoryId?: string, limit = 50) {
  const params = new URLSearchParams();
  if (planId) params.set('plan_id', planId);
  if (repositoryId) params.set('repository_id', repositoryId);
  params.set('limit', String(limit));
  return request<Array<Record<string, any>>>(`/api/v4/checkpoints?${params}`);
}

export async function v4Rollback(checkpointId: string, dryRun = false) {
  return request<Record<string, any>>(`/api/v4/rollback`, {
    method: 'POST', body: JSON.stringify({ checkpoint_id: checkpointId, dry_run: dryRun }),
  });
}

export async function v4ListExecutionLogs(planId?: string, level?: string, limit = 100) {
  const params = new URLSearchParams();
  if (planId) params.set('plan_id', planId);
  if (level) params.set('level', level);
  params.set('limit', String(limit));
  return request<Array<Record<string, any>>>(`/api/v4/execution/logs?${params}`);
}

export async function v4ListRollbackHistory(planId?: string, limit = 50) {
  const params = new URLSearchParams();
  if (planId) params.set('plan_id', planId);
  params.set('limit', String(limit));
  return request<Array<Record<string, any>>>(`/api/v4/rollback/history?${params}`);
}

// ── Phase 5 (v6) Autonomous API ────────────────────────────────────────────

export async function v6CreateTask(payload: {
  objective: string;
  repository_id?: string;
  mode?: string;
  max_repair_attempts?: number;
}) {
  return request<Record<string, any>>('/api/v6/tasks', { method: 'POST', body: JSON.stringify(payload) });
}

export async function v6ListTasks(status?: string, limit = 50) {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  params.set('limit', String(limit));
  return request<Record<string, any>>(`/api/v6/tasks?${params.toString()}`);
}

export async function v6GetTask(taskId: string) {
  return request<Record<string, any>>(`/api/v6/tasks/${taskId}`);
}

export async function v6ExecuteTask(taskId: string) {
  return request<Record<string, any>>(`/api/v6/tasks/${taskId}/execute`, { method: 'POST' });
}

export async function v6TaskAction(taskId: string, action: 'pause' | 'resume' | 'cancel') {
  return request<Record<string, any>>(`/api/v6/tasks/${taskId}/action`, {
    method: 'POST',
    body: JSON.stringify({ action }),
  });
}

export async function v6GenerateReport(taskId: string) {
  return request<Record<string, any>>(`/api/v6/tasks/${taskId}/report`, { method: 'POST' });
}

export async function v6ListReports(limit = 20) {
  return request<Array<Record<string, any>>>(`/api/v6/reports?limit=${limit}`);
}

export async function v6AnalyzeFailures(errors: string[]) {
  return request<Array<Record<string, any>>>('/api/v6/analyze/failures', {
    method: 'POST', body: JSON.stringify(errors),
  });
}

export async function v6AnalyzeArchitecture(files: Record<string, string>) {
  return request<Array<Record<string, any>>>('/api/v6/analyze/architecture', {
    method: 'POST', body: JSON.stringify(files),
  });
}

export async function v6ScoreAgent(agentName: string, toolResponses: unknown[], errors: string[]) {
  return request<Record<string, any>>('/api/v6/agents/score', {
    method: 'POST',
    body: JSON.stringify({ agent_name: agentName, tool_responses: toolResponses, errors }),
  });
}

export async function v6ListPatterns(category?: string) {
  const params = category ? `?category=${category}` : '';
  return request<Array<Record<string, any>>>(`/api/v6/patterns${params}`);
}

export async function v6SearchPatterns(q: string) {
  return request<Array<Record<string, any>>>(`/api/v6/patterns/search?q=${encodeURIComponent(q)}`);
}

export async function v6SearchExperiences(q: string) {
  return request<Array<Record<string, any>>>(`/api/v6/experiences/search?q=${encodeURIComponent(q)}`);
}

// ── Phase 6 (v7) Evolution Engine API ──────────────────────────────────────

export async function v7FullAnalysis(payload: {
  files: Record<string, string>;
  requirements_content?: string;
  imports?: string[];
  repository_id?: string;
  current_version?: string;
}) {
  return request<Record<string, any>>('/api/v7/analyze/full', {
    method: 'POST', body: JSON.stringify(payload),
  });
}

export async function v7AnalyzeDebt(files: Record<string, string>) {
  return request<Record<string, any>>('/api/v7/analyze/debt', {
    method: 'POST', body: JSON.stringify({ files }),
  });
}

export async function v7AnalyzeArchitecture(files: Record<string, string>) {
  return request<Record<string, any>>('/api/v7/analyze/architecture', {
    method: 'POST', body: JSON.stringify({ files }),
  });
}

export async function v7AnalyzeDependencies(content: string) {
  return request<Record<string, any>>('/api/v7/analyze/dependencies/requirements', {
    method: 'POST', body: JSON.stringify({ content }),
  });
}

export async function v7AnalyzePerformance(files: Record<string, string>) {
  return request<Record<string, any>>('/api/v7/analyze/performance', {
    method: 'POST', body: JSON.stringify({ files }),
  });
}

export async function v7AnalyzeSecurity(files: Record<string, string>) {
  return request<Record<string, any>>('/api/v7/analyze/security', {
    method: 'POST', body: JSON.stringify({ files }),
  });
}

export async function v7PlanVersion(payload: {
  current_version: string;
  debt_summary?: Record<string, any>;
  arch_changes?: Record<string, any>[];
  dep_recs?: Record<string, any>[];
  perf_findings?: Record<string, any>[];
  sec_findings?: Record<string, any>[];
}) {
  return request<Record<string, any>>('/api/v7/plan/version', {
    method: 'POST', body: JSON.stringify(payload),
  });
}

export async function v7GetTrends(metric?: string) {
  const params = metric ? `?metric=${metric}` : '';
  return request<Record<string, any>>(`/api/v7/analytics/trends${params}`);
}

export async function v7RecordMetric(metricName: string, value: number, unit = '') {
  return request<Record<string, any>>(`/api/v7/analytics/record?metric_name=${encodeURIComponent(metricName)}&value=${value}&unit=${encodeURIComponent(unit)}`, {
    method: 'POST',
  });
}

export async function v7ListRecommendations(status?: string, grouped = false) {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (grouped) params.set('grouped', 'true');
  return request<Record<string, any>>(`/api/v7/recommendations${params.toString() ? `?${params}` : ''}`);
}

export async function v7GetRecommendationStats() {
  return request<Record<string, any>>('/api/v7/recommendations/stats');
}

export async function v7RecommendationAction(recId: string, action: 'approve' | 'dismiss') {
  return request<Record<string, any>>(`/api/v7/recommendations/${recId}/action`, {
    method: 'POST', body: JSON.stringify({ action }),
  });
}
