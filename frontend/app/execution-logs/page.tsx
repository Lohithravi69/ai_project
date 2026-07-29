"use client";

import { useEffect, useState } from "react";
import { v4ListExecutionLogs } from "../../lib/api";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";

const levelColor: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  info: "default",
  warn: "secondary",
  error: "destructive",
  debug: "outline",
};

export default function ExecutionLogsPage() {
  const [logs, setLogs] = useState<Array<Record<string, any>>>([]);
  const [loading, setLoading] = useState(true);
  const [levelFilter, setLevelFilter] = useState("");

  async function load() {
    setLoading(true);
    try {
      const data = await v4ListExecutionLogs(undefined, levelFilter || undefined);
      setLogs(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [levelFilter]);

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Execution Logs</h1>
      <div className="flex gap-2 items-center">
        <select className="border rounded-md px-2 py-1 text-sm" value={levelFilter} onChange={(e) => setLevelFilter(e.currentTarget.value)}>
          <option value="">All levels</option>
          <option value="info">info</option>
          <option value="warn">warn</option>
          <option value="error">error</option>
          <option value="debug">debug</option>
        </select>
        <span className="text-sm text-muted-foreground">{logs.length} entries</span>
      </div>
      {loading && <p>Loading...</p>}
      {!loading && logs.length === 0 && <p className="text-sm text-muted-foreground">No log entries found.</p>}
      <div className="space-y-1">
        {logs.map((log) => (
          <Card key={log.id}>
            <div className="p-3 flex items-start gap-3">
              <Badge variant={levelColor[log.level] || "outline"} className="shrink-0 mt-0.5">{log.level}</Badge>
              <div className="min-w-0 flex-1">
                <p className="text-sm">{log.message}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  {log.created_at && new Date(log.created_at).toLocaleString()}
                </p>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
