"use client";

import { useMemo, useState } from "react";
import { getConversationMemory } from "../../lib/api";

export default function MemoryViewerPage() {
  const [repositoryId, setRepositoryId] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [entries, setEntries] = useState<Array<Record<string, any>>>([]);
  const [selectedEntryId, setSelectedEntryId] = useState("");
  const [searchText, setSearchText] = useState("");
  const [loading, setLoading] = useState(false);

  const selectedEntry = entries.find((entry) => entry.id === selectedEntryId) ?? null;

  const filteredEntries = useMemo(() => {
    if (!searchText.trim()) {
      return entries;
    }
    const query = searchText.toLowerCase();
    return entries.filter((entry) => {
      return [entry.memory_type, entry.content, entry.session_id, entry.repository_id].some((value) =>
        String(value ?? "").toLowerCase().includes(query),
      );
    });
  }, [entries, searchText]);

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

      <div className="mb-4">
        <input
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          placeholder="Search memory content, repository ID, session ID, or type"
          className="border p-2 rounded w-full"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded">
          <h2 className="font-medium mb-3">Conversation Memory ({filteredEntries.length} entries)</h2>
          {filteredEntries.length === 0 ? (
            <p className="text-muted-foreground">No memory entries found.</p>
          ) : (
            <div className="space-y-3 max-h-[34rem] overflow-auto">
              {filteredEntries.map((entry: any) => (
                <button
                  key={entry.id}
                  onClick={() => setSelectedEntryId(entry.id)}
                  className="w-full text-left border-l-4 border-blue-500 pl-3 py-2 rounded hover:bg-slate-50"
                >
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
                    {entry.content.substring(0, 180)}
                    {entry.content.length > 180 ? "..." : ""}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white p-4 rounded lg:col-span-2">
          <h2 className="font-medium mb-3">Memory Details</h2>
          {selectedEntry ? (
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div><span className="font-medium">Type:</span> {selectedEntry.memory_type}</div>
                <div><span className="font-medium">Created:</span> {selectedEntry.created_at}</div>
                <div><span className="font-medium">Repository:</span> {selectedEntry.repository_id ?? "-"}</div>
                <div><span className="font-medium">Session:</span> {selectedEntry.session_id ?? "-"}</div>
              </div>
              <div>
                <span className="font-medium">Content</span>
                <pre className="mt-2 whitespace-pre-wrap rounded bg-slate-50 p-4 max-h-[28rem] overflow-auto">
                  {selectedEntry.content}
                </pre>
              </div>
              <div>
                <span className="font-medium">Metadata</span>
                <pre className="mt-2 rounded bg-slate-50 p-4 overflow-auto text-xs">
                  {JSON.stringify(selectedEntry.metadata_json ?? {}, null, 2)}
                </pre>
              </div>
            </div>
          ) : (
            <p className="text-muted-foreground">Select a memory entry to inspect its full content and metadata.</p>
          )}
        </div>
      </div>
    </div>
  );
}
