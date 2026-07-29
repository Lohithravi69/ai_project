"use client";

import { useState } from "react";
import { ragChat } from "../../lib/api";

export default function RagChatPage() {
  const [query, setQuery] = useState("");
  const [repositoryId, setRepositoryId] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [sources, setSources] = useState<Array<Record<string, unknown>>>([]);
  const [debug, setDebug] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSend() {
    setLoading(true);
    setAnswer(null);
    setSources([]);
    setDebug(null);
    try {
      const res = await ragChat(query, repositoryId || undefined);
      setAnswer(res.answer);
      setSources(res.sources ?? []);
      setDebug(res.debug ?? null);
    } catch (err: any) {
      setAnswer(`Error: ${err?.message ?? String(err)}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-4">RAG Chat</h1>
      <div className="mb-4 flex flex-col gap-2">
        <input
          value={repositoryId}
          onChange={(e) => setRepositoryId(e.target.value)}
          placeholder="Repository ID (optional)"
          className="border p-2 rounded"
        />
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask a question about the repository or codebase"
          className="border p-2 rounded h-32"
        />
        <div>
          <button disabled={loading || !query} onClick={handleSend} className="btn-primary">
            {loading ? "Thinking…" : "Send"}
          </button>
        </div>
      </div>

      {answer && (
        <section className="mt-6">
          <h2 className="font-medium">Answer</h2>
          <div className="whitespace-pre-wrap bg-white p-4 rounded mt-2">{answer}</div>
        </section>
      )}

      {sources.length > 0 && (
        <section className="mt-6">
          <h3 className="font-medium">Sources</h3>
          <ul className="list-disc pl-5 mt-2">
            {sources.map((s, i) => (
              <li key={i} className="text-sm">
                {JSON.stringify(s)}
              </li>
            ))}
          </ul>
        </section>
      )}

      {debug && (
        <section className="mt-6 rounded border bg-white p-4">
          <h3 className="font-medium">Debug Trace</h3>
          <pre className="mt-2 max-h-[24rem] overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(debug, null, 2)}</pre>
        </section>
      )}
    </div>
  );
}
