"use client";

import { useEffect, useState } from "react";
import { v4ListRollbackHistory, v4Rollback } from "../../lib/api";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";

export default function RollbackHistoryPage() {
  const [entries, setEntries] = useState<Array<Record<string, any>>>([]);
  const [loading, setLoading] = useState(true);
  const [rollingBack, setRollingBack] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const data = await v4ListRollbackHistory();
      setEntries(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleRollback(checkpointId: string) {
    if (!confirm("Rollback to this checkpoint? This will restore git state.")) return;
    setRollingBack(checkpointId);
    try {
      await v4Rollback(checkpointId);
      await load();
    } catch (err) {
      console.error(err);
    } finally {
      setRollingBack(null);
    }
  }

  if (loading) return <div className="p-6">Loading rollback history...</div>;

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Rollback History</h1>
      <p className="text-muted-foreground">{entries.length} rollback entries</p>
      {entries.length === 0 && <p className="text-sm text-muted-foreground">No rollback history yet.</p>}
      <div className="space-y-2">
        {entries.map((entry) => (
          <Card key={entry.id}>
            <div className="p-4 flex items-center justify-between">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Badge variant={entry.status === "completed" ? "default" : entry.status === "failed" ? "destructive" : "outline"}>{entry.status}</Badge>
                  <span className="text-sm font-medium">{entry.rollback_type}</span>
                </div>
                <p className="text-xs text-muted-foreground">{entry.summary}</p>
                <p className="text-xs text-muted-foreground">
                  {entry.restored_branch} @ {entry.restored_git_sha?.slice(0, 8)}
                </p>
              </div>
              <div className="text-right text-xs text-muted-foreground">
                <p>{entry.execution_ms}ms</p>
                <Button size="sm" variant="outline" onClick={() => handleRollback(entry.checkpoint_id)} disabled={rollingBack === entry.checkpoint_id}>
                  Rollback
                </Button>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
