export type Repository = {
  id: string;
  connection_id: string;
  full_name: string;
  clone_url: string;
  local_path: string;
  default_branch: string;
  language_summary: Record<string, unknown>;
  framework_summary: Record<string, unknown>;
  scan_status: string;
  summary: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type FileSummary = {
  id: string;
  repository_id: string;
  path: string;
  language: string;
  summary: string;
  symbols_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ProjectSummary = {
  repository_id: string;
  repository_name: string;
  summary: string;
  language_summary: Record<string, unknown>;
  framework_summary: Record<string, unknown>;
  file_count: number;
  function_count: number;
  class_count: number;
  route_count: number;
};

export type ChatMessage = {
  role: 'user' | 'assistant';
  content: string;
};

export type SearchResult = {
  id: string;
  content: string;
  metadata: Record<string, unknown>;
  score: number;
};
