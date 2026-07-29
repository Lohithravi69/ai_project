"use client";

import { useEffect, useState } from "react";
import { v4ListTools } from "../../lib/api";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";

export default function ToolRegistryPage() {
  const [tools, setTools] = useState<Array<Record<string, any>>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    v4ListTools()
      .then(setTools)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6">Loading tools...</div>;

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Tool Registry</h1>
      <p className="text-muted-foreground">{tools.length} registered tools</p>
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {tools.map((tool) => (
          <Card key={tool.name}>
            <div className="p-4 space-y-2">
              <div className="flex items-center justify-between">
                <h2 className="font-medium">{tool.name}</h2>
                <Badge variant={tool.permission_level === "write" ? "default" : "secondary"}>{tool.permission_level}</Badge>
              </div>
              <p className="text-sm text-muted-foreground">{tool.description}</p>
              <div className="flex gap-2 text-xs text-muted-foreground">
                <span>v{tool.version}</span>
                <span>⏱ {tool.timeout_seconds}s</span>
                {tool.dry_run_support && <span>🧪 dry-run</span>}
                {tool.rollback_support && <span>↩ rollback</span>}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
