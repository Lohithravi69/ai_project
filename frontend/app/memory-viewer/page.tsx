"use client";

import { useState } from "react";
import { getConversationMemory } from "../../lib/api";

export default function MemoryViewerPage() {
  const [repositoryId, setRepositoryId] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [entries, setEntries] = useState<Array<Record<string, any>>>([]);
  const [loading, setLoading] = useState(false);

  async function loadMemory() {
    setLoading(true);
    try {
      const res = await getConversationMemory(repositoryId || undefined, sessionId || undefined, 100);
      setEntries(res.entries || []);
    } catch (err) {
      console.error(err);
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-4">Memory Viewer</h1>
      <div className="mb-4 grid grid-cols-3 gap-2">
        <div>
          <label className="block text-sm font-medium mb-1">Repository ID (optional)</label>
          <input
            value={repositoryId}
            onChange={(e) => setRepositoryId(e.target.value)}
            placeholder="Repository ID"
            className="border p-2 rounded w-full"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Session ID (optional)</label>
          <input
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            placeholder="Session ID"
            className="border p-2 rounded w-full"
          />
        </div>
        <div className="flex items-end">
          <button onClick={loadMemory} disabled={loading} className="btn-primary w-full">
            {loading ? "Loading…" : "Load Memory"}
          </button>
        </div>
      </div>

      <div className="bg-white p-4 rounded">
        <h2 className="font-medium mb-3">Conversation Memory ({entries.length} entries)</h2>
        {entries.length === 0 ? (
          <p className="text-muted-foreground">No memory entries found.</p>
        ) : (
          <div className="space-y-3 max-h-96 overflow-auto">
            {entries.map((entry: any) => (
              <div key={entry.id} className="border-l-4 border-blue-500 pl-3 py-2">
                <div className="flex justify-between items-start">
                  <div>
                    <span className="inline-block bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">
                      {entry.memory_type}
                    </span>
                    {entry.session_id && (
                      <span className="text-xs text-gray-600 ml-2">Session: {entry.session_id}</span>
                    )}
                  </div>
                  <span className="text-xs text-gray-500">{entry.created_at}</span>
                </div>
                <div className="text-sm mt-2 whitespace-pre-wrap text-gray-700 max-w-2xl">
                  {entry.content.substring(0, 500)}
                  {entry.content.length > 500 ? "..." : ""}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
