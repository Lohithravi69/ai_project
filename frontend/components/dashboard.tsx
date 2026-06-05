'use client';

import { useEffect, useMemo, useState } from 'react';

import {
  connectGitHub,
  fetchRepositoryFiles,
  fetchRepositorySummary,
  fetchRepositories,
  queueScan,
  sendChat,
  syncGitHubRepositories,
} from '../lib/api';
import type { ChatMessage, FileSummary, ProjectSummary, Repository } from '../lib/types';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Input } from './ui/input';
import { Progress } from './ui/progress';
import { Textarea } from './ui/textarea';

function formatValue(value: unknown) {
  if (value == null) {
    return '—';
  }
  if (typeof value === 'string' || typeof value === 'number') {
    return String(value);
  }
  return JSON.stringify(value);
}

export function Dashboard() {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [selectedRepositoryId, setSelectedRepositoryId] = useState<string>('');
  const [summary, setSummary] = useState<ProjectSummary | null>(null);
  const [files, setFiles] = useState<FileSummary[]>([]);
  const [chatInput, setChatInput] = useState('Explain this project');
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: 'assistant', content: 'Connect a repository to begin local codebase analysis.' },
  ]);
  const [accountName, setAccountName] = useState('local-dev-account');
  const [githubToken, setGitHubToken] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('Idle');
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const [sessionId, setSessionId] = useState<string | undefined>();

  const selectedRepository = useMemo(
    () => repositories.find((repository) => repository.id === selectedRepositoryId) ?? null,
    [repositories, selectedRepositoryId],
  );

  async function refreshRepositories() {
    const data = await fetchRepositories();
    setRepositories(data);
    if (!selectedRepositoryId && data[0]) {
      setSelectedRepositoryId(data[0].id);
    }
  }

  async function loadRepositoryData(repositoryId: string) {
    const [summaryData, fileData] = await Promise.all([fetchRepositorySummary(repositoryId), fetchRepositoryFiles(repositoryId)]);
    setSummary(summaryData);
    setFiles(fileData);
  }

  useEffect(() => {
    void refreshRepositories().catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!selectedRepositoryId) {
      setSummary(null);
      setFiles([]);
      return;
    }
    void loadRepositoryData(selectedRepositoryId).catch((err: Error) => setError(err.message));
  }, [selectedRepositoryId]);

  async function handleGitHubConnect() {
    setBusy(true);
    setError('');
    setStatus('Connecting GitHub account');
    setProgress(20);
    try {
      const connection = await connectGitHub(accountName, githubToken);
      setStatus('Syncing repositories');
      setProgress(55);
      await syncGitHubRepositories(connection.id, githubToken);
      await refreshRepositories();
      setStatus('GitHub repositories synchronized');
      setProgress(100);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect GitHub');
      setStatus('Connection failed');
    } finally {
      setBusy(false);
      window.setTimeout(() => setProgress(0), 1200);
    }
  }

  async function handleScan(repositoryId: string) {
    setBusy(true);
    setError('');
    setStatus('Queueing repository scan');
    try {
      await queueScan(repositoryId);
      setRepositories((current) => current.map((repo) => (repo.id === repositoryId ? { ...repo, scan_status: 'queued' } : repo)));
      setStatus('Scan queued');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to queue scan');
      setStatus('Scan failed');
    } finally {
      setBusy(false);
    }
  }

  async function handleChatSubmit() {
    if (!selectedRepositoryId || !chatInput.trim()) {
      return;
    }
    const question = chatInput.trim();
    setBusy(true);
    setError('');
    setMessages((current) => [...current, { role: 'user', content: question }]);
    try {
      const response = await sendChat(selectedRepositoryId, question, sessionId);
      setSessionId(response.session_id);
      setMessages((current) => [...current, { role: 'assistant', content: response.answer }]);
      setStatus('Answer generated from repository context');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Chat request failed');
      setMessages((current) => [...current, { role: 'assistant', content: 'I could not generate an answer for that repository.' }]);
    } finally {
      setBusy(false);
    }
  }

  const repoStats = [
    { label: 'Repositories', value: repositories.length },
    { label: 'Files indexed', value: files.length },
    { label: 'File count', value: summary?.file_count ?? 0 },
    { label: 'Functions', value: summary?.function_count ?? 0 },
  ];

  return (
    <main className="min-h-screen px-4 py-6 text-white md:px-8 lg:px-10">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-6">
        <section className="surface rounded-[2rem] p-6 md:p-8">
          <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
            <div className="space-y-4">
              <Badge className="w-fit border-[rgba(245,158,11,0.3)] bg-[rgba(245,158,11,0.12)] text-[hsl(var(--accent))]">Local AI Development OS</Badge>
              <h1 className="max-w-3xl text-4xl font-semibold tracking-tight md:text-6xl">Repository intelligence, cloned locally, explained with RAG, and powered by open-source tooling.</h1>
              <p className="max-w-2xl text-sm leading-6 text-white/[0.62] md:text-base">Connect GitHub, sync repositories, scan code with structured parsing, persist embeddings in ChromaDB, and ask architecture questions from a single local workspace.</p>
              <div className="flex flex-wrap gap-3">
                {repoStats.map((item) => (
                  <Card key={item.label} className="min-w-[150px] bg-white/[0.03] p-4">
                    <CardDescription>{item.label}</CardDescription>
                    <CardTitle className="mt-1 text-3xl">{item.value}</CardTitle>
                  </Card>
                ))}
              </div>
            </div>
            <Card className="bg-white/[0.04]">
              <CardHeader>
                <div>
                  <CardTitle>GitHub Connection</CardTitle>
                  <CardDescription>Attach a token, sync repositories, then start scanning.</CardDescription>
                </div>
                <Badge>Phase 1</Badge>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <Input value={accountName} onChange={(event) => setAccountName(event.target.value)} placeholder="GitHub account name" />
                  <Input value={githubToken} onChange={(event) => setGitHubToken(event.target.value)} placeholder="GitHub token" type="password" />
                  <Button disabled={busy || !githubToken.trim()} onClick={() => void handleGitHubConnect()}>Connect and sync</Button>
                </div>
                <div className="mt-4 space-y-2">
                  <Progress value={progress} />
                  <p className="text-xs text-white/[0.55]">{status}</p>
                  {error ? <p className="rounded-xl border border-red-400/30 bg-red-500/10 px-3 py-2 text-xs text-red-200">{error}</p> : null}
                </div>
              </CardContent>
            </Card>
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-[360px_1fr]">
          <Card className="bg-white/[0.04]">
            <CardHeader>
              <div>
                <CardTitle>Repositories</CardTitle>
                <CardDescription>Choose a project to inspect, scan, or query.</CardDescription>
              </div>
              <Button variant="secondary" onClick={() => void refreshRepositories()}>Refresh</Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {repositories.length === 0 ? (
                  <p className="rounded-2xl border border-dashed border-white/10 bg-white/[0.03] p-4 text-sm text-white/50">No repositories indexed yet. Connect GitHub to populate the workspace.</p>
                ) : (
                  repositories.map((repository) => (
                    <button
                      key={repository.id}
                      onClick={() => setSelectedRepositoryId(repository.id)}
                      className={`w-full rounded-2xl border px-4 py-3 text-left transition ${selectedRepositoryId === repository.id ? 'border-[rgba(245,158,11,0.5)] bg-[rgba(245,158,11,0.1)]' : 'border-white/10 bg-white/[0.03] hover:bg-white/[0.06]'}`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="font-medium text-white">{repository.full_name}</p>
                          <p className="text-xs text-white/50">{repository.local_path}</p>
                        </div>
                        <Badge>{repository.scan_status}</Badge>
                      </div>
                    </button>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
            <Card className="bg-white/[0.04]">
              <CardHeader>
                <div>
                  <CardTitle>Project Summary</CardTitle>
                  <CardDescription>{selectedRepository?.full_name ?? 'No repository selected'}</CardDescription>
                </div>
                {selectedRepository ? <Button variant="secondary" onClick={() => void handleScan(selectedRepository.id)} disabled={busy}>Scan repository</Button> : null}
              </CardHeader>
              <CardContent>
                {summary ? (
                  <div className="space-y-4">
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                      {[
                        ['Files', summary.file_count],
                        ['Functions', summary.function_count],
                        ['Classes', summary.class_count],
                        ['Routes', summary.route_count],
                      ].map(([label, value]) => (
                        <Card key={label as string} className="bg-white/[0.03] p-4">
                          <CardDescription>{label}</CardDescription>
                          <CardTitle className="mt-1 text-2xl">{value as number}</CardTitle>
                        </Card>
                      ))}
                    </div>
                    <div className="rounded-3xl border border-white/10 bg-black/20 p-4">
                      <p className="label mb-2">Narrative</p>
                      <p className="text-sm leading-6 text-white/[0.74] whitespace-pre-wrap">{summary.summary || 'Scan the repository to generate a project summary.'}</p>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="rounded-3xl border border-white/10 bg-black/20 p-4">
                        <p className="label mb-3">Languages</p>
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(summary.language_summary).map(([language, value]) => (
                            <Badge key={language}>{language}: {formatValue(value)}</Badge>
                          ))}
                        </div>
                      </div>
                      <div className="rounded-3xl border border-white/10 bg-black/20 p-4">
                        <p className="label mb-3">Frameworks</p>
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(summary.framework_summary).map(([framework, value]) => (
                            <Badge key={framework}>{framework}: {formatValue(value)}</Badge>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-3xl border border-dashed border-white/10 bg-white/[0.03] p-6 text-sm text-white/50">Select a repository to see its structural summary.</div>
                )}
              </CardContent>
            </Card>

            <Card className="bg-white/[0.04]">
              <CardHeader>
                <div>
                  <CardTitle>File Explorer</CardTitle>
                  <CardDescription>{files.length} indexed file summaries</CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <div className="max-h-[520px] space-y-3 overflow-auto pr-1">
                  {files.length === 0 ? (
                    <p className="rounded-2xl border border-dashed border-white/10 bg-white/[0.03] p-4 text-sm text-white/50">File summaries appear here after scanning.</p>
                  ) : (
                    files.map((file) => (
                      <div key={file.id} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-medium text-white">{file.path}</p>
                            <p className="text-xs text-white/[0.45]">{file.language}</p>
                          </div>
                          <Badge>{file.language}</Badge>
                        </div>
                        <p className="mt-3 text-sm leading-6 text-white/[0.72]">{file.summary || 'No symbols detected yet.'}</p>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <Card className="bg-white/[0.04]">
            <CardHeader>
              <div>
                <CardTitle>Chat with repository</CardTitle>
                <CardDescription>Ask architecture, security, API, and bug-finding questions.</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <Textarea value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder="How does authentication work?" />
                <Button disabled={busy || !selectedRepositoryId} onClick={() => void handleChatSubmit()}>Ask repository</Button>
                <div className="space-y-3 rounded-3xl border border-white/10 bg-black/20 p-4">
                  {messages.map((message, index) => (
                    <div key={`${message.role}-${index}`} className={`rounded-2xl px-4 py-3 ${message.role === 'assistant' ? 'bg-white/[0.04]' : 'bg-[hsl(var(--accent))]/10'}`}>
                      <p className="label mb-2">{message.role}</p>
                      <p className="text-sm leading-6 text-white/[0.82] whitespace-pre-wrap">{message.content}</p>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white/[0.04]">
            <CardHeader>
              <div>
                <CardTitle>Inspector</CardTitle>
                <CardDescription>Current repository signals and runtime status.</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4 text-sm text-white/70">
                <div className="rounded-3xl border border-white/10 bg-black/20 p-4">
                  <p className="label mb-2">Selected Repository</p>
                  <p className="font-medium text-white">{selectedRepository?.full_name ?? 'None'}</p>
                  <p className="mt-1 text-xs text-white/50">{selectedRepository?.local_path ?? 'Waiting for GitHub sync'}</p>
                </div>
                <div className="rounded-3xl border border-white/10 bg-black/20 p-4">
                  <p className="label mb-2">Framework Summary</p>
                  <pre className="overflow-auto text-xs leading-6 text-white/70">{JSON.stringify(selectedRepository?.framework_summary ?? {}, null, 2)}</pre>
                </div>
                <div className="rounded-3xl border border-white/10 bg-black/20 p-4">
                  <p className="label mb-2">Language Summary</p>
                  <pre className="overflow-auto text-xs leading-6 text-white/70">{JSON.stringify(selectedRepository?.language_summary ?? {}, null, 2)}</pre>
                </div>
              </div>
            </CardContent>
          </Card>
        </section>
      </div>
    </main>
  );
}
