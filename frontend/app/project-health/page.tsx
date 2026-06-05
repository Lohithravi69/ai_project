"use client";

import { useState } from "react";
import { projectHealth } from "../../lib/api";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";

export default function ProjectHealthPage() {
  const [repoId, setRepoId] = useState("");
  const [report, setReport] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);

  async function runHealth() {
    setLoading(true);
    try {
      const res = await projectHealth(repoId);
      setReport(res.report);
    } catch (err) {
      console.error(err);
      setReport(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-semibold mb-4">Project Health</h1>
      <div className="flex gap-2 mb-4">
        <Input value={repoId} onChange={(e) => setRepoId(e.currentTarget.value)} placeholder="Repository ID" />
        <Button onClick={runHealth} disabled={loading || !repoId}>{loading ? "Running..." : "Run"}</Button>
      </div>
      {report && (
        <Card>
          <div className="p-4">
            <pre className="whitespace-pre-wrap text-sm">{JSON.stringify(report, null, 2)}</pre>
          </div>
        </Card>
      )}
    </div>
  );
}
