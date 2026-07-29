"use client";

import { useEffect, useState } from "react";
import { v4ListWorkspaces } from "../../lib/api";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";

const statusColor: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  created: "outline",
  cloned: "secondary",
  committed: "default",
  pushed: "default",
  destroyed: "destructive",
};

export default function WorkspaceManagerPage() {
  const [workspaces, setWorkspaces] = useState<Array<Record<string, any>>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    v4ListWorkspaces()
      .then(setWorkspaces)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6">Loading workspaces...</div>;

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Workspace Manager</h1>
      <p className="text-muted-foreground">{workspaces.length} workspaces</p>
      {workspaces.length === 0 && <p className="text-sm text-muted-foreground">No workspaces yet.</p>}
      <div className="space-y-3">
        {workspaces.map((ws) => (
          <Card key={ws.id}>
            <div className="p-4">
              <div className="flex items-center justify-between mb-2">
                <h2 className="font-medium">{ws.repository_full_name || ws.id.slice(0, 8)}</h2>
                <Badge variant={statusColor[ws.status] || "outline"}>{ws.status}</Badge>
              </div>
              <div className="text-xs text-muted-foreground space-y-1">
                <p>Branch: {ws.branch_name} ← {ws.base_branch}</p>
                <p>Path: {ws.workspace_path}</p>
                {ws.commit_sha && <p>Commit: {ws.commit_sha.slice(0, 8)}</p>}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
