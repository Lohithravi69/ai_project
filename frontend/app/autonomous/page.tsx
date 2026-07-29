"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { v6CreateTask, v6ListTasks } from "../../lib/api";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Badge } from "../../components/ui/badge";

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  cancelled: "bg-gray-100 text-gray-800",
  repairing: "bg-purple-100 text-purple-800",
  paused: "bg-orange-100 text-orange-800",
};

export default function AutonomousPage() {
  const router = useRouter();
  const [tasks, setTasks] = useState<Record<string, any>[]>([]);
  const [objective, setObjective] = useState("");
  const [mode, setMode] = useState("full");
  const [repositoryId, setRepositoryId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadTasks() {
    try {
      const data = await v6ListTasks();
      setTasks(data.tasks || data || []);
    } catch { /* ignore */ }
  }

  useEffect(() => { loadTasks(); }, []);

  async function handleCreate() {
    if (!objective.trim()) return;
    setLoading(true);
    setError("");
    try {
      const task = await v6CreateTask({
        objective: objective.trim(),
        repository_id: repositoryId.trim(),
        mode,
      });
      router.push(`/autonomous/${task.id}`);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Autonomous Development</h1>
      <p className="text-muted-foreground">Create and manage autonomous engineering tasks.</p>

      <Card>
        <div className="p-4 space-y-3">
          <Input value={objective} onChange={(e) => setObjective(e.currentTarget.value)} placeholder="What should the autonomous system do?" />
          <div className="flex gap-2">
            <select value={mode} onChange={(e) => setMode(e.currentTarget.value)} className="border rounded-md px-3 py-2 text-sm">
              <option value="full">Full Pipeline</option>
              <option value="plan-only">Plan Only</option>
              <option value="code-only">Code Only</option>
            </select>
            <Input value={repositoryId} onChange={(e) => setRepositoryId(e.currentTarget.value)} placeholder="Repository ID (optional)" />
          </div>
          <Button onClick={handleCreate} disabled={loading || !objective.trim()}>
            {loading ? "Creating..." : "Create Task"}
          </Button>
        </div>
      </Card>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      <div className="space-y-2">
        <h2 className="text-lg font-medium">Tasks</h2>
        {tasks.length === 0 && <p className="text-muted-foreground text-sm">No tasks yet.</p>}
        {tasks.map((task: Record<string, any>) => (
          <Card key={task.id} className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => router.push(`/autonomous/${task.id}`)}>
            <div className="p-4 flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate">{task.objective}</p>
                <p className="text-sm text-muted-foreground">{task.id?.slice(0, 8)}... | {task.mode}</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge className={STATUS_COLORS[task.status] || ""}>{task.status}</Badge>
                <span className="text-xs text-muted-foreground">{task.repair_attempts > 0 ? `Repairs: ${task.repair_attempts}` : ""}</span>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
