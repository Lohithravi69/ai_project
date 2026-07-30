"use client";

import { useState } from "react";
import { ragChat } from "../../lib/api";

export default function RetrievalDebuggerPage() {
  const [query, setQuery] = useState("");
  const [repositoryId, setRepositoryId] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [debug, setDebug] = useState<Record<string, any> | null>(null);
  const [sources, setSources] = useState<Array<Record<string, any>>>([]);
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);

  async function runDebug() {
    setLoading(true);
    setDebug(null);
    setSources([]);
    try {
      const response = await ragChat(query, repositoryId || undefined, sessionId || undefined, 8);
      setAnswer(response.answer);
      setSources(response.sources || []);
      setDebug(response.debug || null);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4 p-6">
      <h1 className="text-2xl font-semibold">Retrieval Debugger</h1>
      <div className="grid gap-2 md:grid-cols-3">
        <input className="border p-2 rounded" placeholder="Repository ID (optional)" value={repositoryId} onChange={(e) => setRepositoryId(e.target.value)} />
        <input className="border p-2 rounded" placeholder="Session ID (optional)" value={sessionId} onChange={(e) => setSessionId(e.target.value)} />
        <button className="btn-primary" onClick={runDebug} disabled={loading || !query.trim()}>{loading ? "Running…" : "Debug Retrieval"}</button>
      </div>
      <textarea className="border p-2 rounded w-full h-28" placeholder="Ask a code question" value={query} onChange={(e) => setQuery(e.target.value)} />

      {answer ? (
        <section className="space-y-2 rounded-lg border p-4">
          <h2 className="font-medium">Answer</h2>
          <pre className="whitespace-pre-wrap text-sm">{answer}</pre>
        </section>
      ) : null}

      {debug ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="space-y-2 rounded-lg border p-4">
            <h2 className="font-medium">Prompt Context</h2>
            <pre className="max-h-[30rem] overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-3 text-xs">{debug.prompt_context as string}</pre>
          </section>
          <section className="space-y-2 rounded-lg border p-4">
            <h2 className="font-medium">Token & Context Stats</h2>
            <ul className="space-y-1 text-sm">
              <li>Prompt tokens: {String(debug.prompt_tokens ?? 0)}</li>
              <li>Completion tokens: {String(debug.completion_tokens ?? 0)}</li>
              <li>Context size: {String(debug.context_size ?? 0)}</li>
              <li>Retrieved chunks: {String(debug.retrieved_chunk_count ?? 0)}</li>
              <li>Response time: {String(debug.response_time_ms ?? 0)} ms</li>
              <li>Estimated model memory: {String(debug.estimated_local_model_memory_mb ?? 0)} MB</li>
            </ul>
          </section>
          <section className="space-y-2 rounded-lg border p-4 lg:col-span-2">
            <h2 className="font-medium">Retrieved Chunks</h2>
            <div className="space-y-3">
              {(debug.retrieved_chunks as Array<Record<string, any>> | undefined)?.map((chunk, index) => (
                <div key={`${chunk.id ?? index}`} className="rounded border bg-white p-3 text-sm">
                  <div className="flex flex-wrap gap-3 text-xs text-gray-600">
                    <span>Chunk: {String(chunk.id ?? "-")}</span>
                    <span>Score: {String(chunk.score ?? 0)}</span>
                    <span>Repository: {String(chunk.metadata?.repository_id ?? repositoryId ?? "-")}</span>
                    <span>File: {String(chunk.metadata?.path ?? chunk.metadata?.file_path ?? "-")}</span>
                  </div>
                  <pre className="mt-2 whitespace-pre-wrap text-xs text-gray-800">{String(chunk.content ?? "")}</pre>
                </div>
              ))}
            </div>
          </section>
          <section className="space-y-2 rounded-lg border p-4 lg:col-span-2">
            <h2 className="font-medium">Sources</h2>
            <pre className="max-h-[20rem] overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-3 text-xs">{JSON.stringify(sources, null, 2)}</pre>
          </section>
        </div>
      ) : null}
    </div>
  );
}
