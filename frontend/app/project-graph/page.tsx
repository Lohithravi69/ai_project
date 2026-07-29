"use client";

import { useMemo, useState } from "react";
import { projectGraph } from "../../lib/api";

export default function ProjectGraphPage() {
  const [repositoryId, setRepositoryId] = useState("");
  const [nodes, setNodes] = useState<Array<Record<string, any>>>([]);
  const [edges, setEdges] = useState<Array<Record<string, any>>>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string>("");
  const [filterText, setFilterText] = useState("");
  const [loading, setLoading] = useState(false);

  const selectedNode = nodes.find((node) => node.node_id === selectedNodeId) ?? null;

  const filteredNodes = useMemo(() => {
    if (!filterText.trim()) {
      return nodes;
    }
    const query = filterText.toLowerCase();
    return nodes.filter((node) => {
      return [node.name, node.node_type, node.canonical_path].some((value) =>
        String(value ?? "").toLowerCase().includes(query),
      );
    });
  }, [filterText, nodes]);

  const filteredEdges = useMemo(() => {
    if (!selectedNodeId) {
      return edges;
    }
    return edges.filter((edge) => edge.from_node === selectedNodeId || edge.to_node === selectedNodeId);
  }, [edges, selectedNodeId]);

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

      <div className="mb-4">
        <input
          value={filterText}
          onChange={(e) => setFilterText(e.target.value)}
          placeholder="Filter nodes by name, type, or path"
          className="border p-2 rounded w-full"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded">
          <h2 className="font-medium mb-2">Nodes ({filteredNodes.length})</h2>
          <ul className="text-sm list-disc pl-5 max-h-96 overflow-auto">
            {filteredNodes.map((n) => (
              <li key={n.node_id} className="mb-2">
                <button
                  className="text-left w-full rounded border px-2 py-1 hover:bg-slate-50"
                  onClick={() => setSelectedNodeId(n.node_id)}
                >
                  <strong>{n.name}</strong> <span className="text-muted-foreground">({n.node_type})</span>
                  <div className="text-xs text-gray-600">{n.canonical_path}</div>
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div className="bg-white p-4 rounded">
          <h2 className="font-medium mb-2">Details</h2>
          {selectedNode ? (
            <div className="space-y-2 text-sm">
              <div><span className="font-medium">Name:</span> {selectedNode.name}</div>
              <div><span className="font-medium">Type:</span> {selectedNode.node_type}</div>
              <div><span className="font-medium">Path:</span> {selectedNode.canonical_path}</div>
              <pre className="rounded bg-slate-50 p-3 text-xs overflow-auto">
                {JSON.stringify(selectedNode.metadata_json ?? {}, null, 2)}
              </pre>
            </div>
          ) : (
            <p className="text-sm text-gray-600">Select a node to inspect its metadata and related edges.</p>
          )}
        </div>
        <div className="bg-white p-4 rounded">
          <h2 className="font-medium mb-2">Related Edges ({filteredEdges.length})</h2>
          <ul className="text-sm list-disc pl-5 max-h-96 overflow-auto">
            {filteredEdges.map((e) => (
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
