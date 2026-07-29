"use client";

import { useState } from "react";
import { v4CreatePlan } from "../../lib/api";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";

export default function ExecutionPlannerPage() {
  const [objective, setObjective] = useState("");
  const [requestText, setRequestText] = useState("");
  const [repoIds, setRepoIds] = useState("");
  const [files, setFiles] = useState("");
  const [plan, setPlan] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleCreate() {
    setLoading(true);
    setError("");
    try {
      const result = await v4CreatePlan({
        objective,
        request_text: requestText,
        repository_ids: repoIds ? repoIds.split(",").map((s) => s.trim()) : [],
        affected_files: files ? files.split(",").map((s) => s.trim()) : [],
      });
      setPlan(result);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Execution Planner</h1>
      <p className="text-muted-foreground">Convert a request into an executable plan.</p>
      <Card>
        <div className="p-4 space-y-3">
          <Input value={objective} onChange={(e) => setObjective(e.currentTarget.value)} placeholder="Objective (e.g. Update authentication module)" />
          <textarea
            className="w-full border rounded-md p-2 text-sm min-h-[80px]"
            value={requestText}
            onChange={(e) => setRequestText(e.currentTarget.value)}
            placeholder="Describe what you want to do..."
          />
          <Input value={repoIds} onChange={(e) => setRepoIds(e.currentTarget.value)} placeholder="Repository IDs (comma-separated, optional)" />
          <Input value={files} onChange={(e) => setFiles(e.currentTarget.value)} placeholder="Affected files (comma-separated, optional)" />
          <Button onClick={handleCreate} disabled={loading || !objective || !requestText}>
            {loading ? "Creating..." : "Create Plan"}
          </Button>
        </div>
      </Card>
      {error && <p className="text-red-500 text-sm">{error}</p>}
      {plan && (
        <Card>
          <div className="p-4 space-y-2">
            <h2 className="text-lg font-medium">Plan: {plan.id}</h2>
            <p><span className="font-medium">Risk:</span> {plan.risk_score}</p>
            <p><span className="font-medium">Status:</span> {plan.approval_status}</p>
            <p><span className="font-medium">Approval Required:</span> {String(plan.approval_required)}</p>
            <p><span className="font-medium">Tools:</span> {(plan.required_tools || []).join(", ")}</p>
            <p><span className="font-medium">Rollback:</span> {plan.rollback_strategy}</p>
          </div>
        </Card>
      )}
    </div>
  );
}
