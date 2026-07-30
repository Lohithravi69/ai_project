"use client";

import { useState } from "react";
import { analyzeRepository } from "../../lib/api";

export default function RepositoryKnowledgePage() {
  const [repositoryId, setRepositoryId] = useState("");
  const [report, setReport] = useState<{ nodes?: number; edges?: number } | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleAnalyze() {
    setLoading(true);
    setReport(null);
    try {
      const res = await analyzeRepository(repositoryId);
      setReport(res);
    } catch (err: any) {
      setReport({ nodes: 0, edges: 0 });
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-4">Repository Knowledge</h1>
      <div className="mb-4 flex gap-2">
        <input
          value={repositoryId}
          onChange={(e) => setRepositoryId(e.target.value)}
          placeholder="Repository ID"
          className="border p-2 rounded flex-1"
        />
        <button onClick={handleAnalyze} disabled={loading || !repositoryId} className="btn-primary">
          {loading ? "Analyzing…" : "Analyze"}
        </button>
      </div>

      {report && (
        <div className="bg-white p-4 rounded">
          <p>Nodes: {report.nodes ?? 0}</p>
          <p>Edges: {report.edges ?? 0}</p>
          <p className="text-sm text-muted-foreground mt-2">Use the Project Graph visualizer to explore nodes and edges.</p>
        </div>
      )}
    </div>
  );
}
