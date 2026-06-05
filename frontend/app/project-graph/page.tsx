"use client";

import { useState } from "react";
import { projectGraph } from "../../lib/api";

export default function ProjectGraphPage() {
  const [repositoryId, setRepositoryId] = useState("");
  const [nodes, setNodes] = useState<Array<Record<string, any>>>([]);
  const [edges, setEdges] = useState<Array<Record<string, any>>>([]);
  const [loading, setLoading] = useState(false);

  async function loadGraph() {
    setLoading(true);
    try {
      const res = await projectGraph(repositoryId);
      setNodes(res.nodes || []);
      setEdges(res.edges || []);
    } catch (err) {
      console.error(err);
      setNodes([]);
      setEdges([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-4">Project Graph</h1>
      <div className="mb-4 flex gap-2">
        <input
          value={repositoryId}
          onChange={(e) => setRepositoryId(e.target.value)}
          placeholder="Repository ID"
          className="border p-2 rounded flex-1"
        />
        <button onClick={loadGraph} disabled={loading || !repositoryId} className="btn-primary">
          {loading ? "Loading…" : "Load Graph"}
        </button>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white p-4 rounded">
          <h2 className="font-medium mb-2">Nodes ({nodes.length})</h2>
          <ul className="text-sm list-disc pl-5 max-h-96 overflow-auto">
            {nodes.map((n) => (
              <li key={n.node_id}>
                <strong>{n.name}</strong> <span className="text-muted-foreground">({n.node_type})</span>
                <div className="text-xs text-gray-600">{n.canonical_path}</div>
              </li>
            ))}
          </ul>
        </div>
        <div className="bg-white p-4 rounded">
          <h2 className="font-medium mb-2">Edges ({edges.length})</h2>
          <ul className="text-sm list-disc pl-5 max-h-96 overflow-auto">
            {edges.map((e) => (
              <li key={e.edge_id}>
                <span className="text-xs text-gray-700">{e.edge_type}</span> — <em>{e.from_node}</em> → <em>{e.to_node}</em>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
