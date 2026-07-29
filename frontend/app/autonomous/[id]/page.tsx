"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { v6GetTask, v6ExecuteTask, v6TaskAction, v6GenerateReport, v6ListReports } from "../../../lib/api";
import { Button } from "../../../components/ui/button";
import { Card } from "../../../components/ui/card";
import { Badge } from "../../../components/ui/badge";

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  cancelled: "bg-gray-100 text-gray-800",
  repairing: "bg-purple-100 text-purple-800",
  paused: "bg-orange-100 text-orange-800",
};

export default function TaskDetailPage() {
  const params = useParams();
  const router = useRouter();
  const taskId = params.id as string;

  const [task, setTask] = useState<Record<string, any> | null>(null);
  const [report, setReport] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState("");

  async function loadTask() {
    try {
      const data = await v6GetTask(taskId);
      setTask(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadTask(); }, [taskId]);

  async function handleExecute() {
    setExecuting(true);
    setError("");
    try {
      const result = await v6ExecuteTask(taskId);
      await loadTask();
    } catch (err) {
      setError(String(err));
    } finally {
      setExecuting(false);
    }
  }

  async function handleAction(action: "pause" | "resume" | "cancel") {
    try {
      await v6TaskAction(taskId, action);
      await loadTask();
    } catch (err) {
      setError(String(err));
    }
  }

  async function handleReport() {
    try {
      const r = await v6GenerateReport(taskId);
      setReport(r);
    } catch (err) {
      setError(String(err));
    }
  }

  if (loading) return <div className="p-6">Loading...</div>;
  if (!task) return <div className="p-6 text-red-500">Task not found: {error}</div>;

  const canExecute = task.status === "pending" || task.status === "paused";
  const canCancel = task.status === "running" || task.status === "pending" || task.status === "paused";
  const canPause = task.status === "running";
  const canResume = task.status === "paused";

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-2">
        <Button variant="outline" onClick={() => router.push("/autonomous")}>Back</Button>
        <h1 className="text-2xl font-semibold">Task Detail</h1>
      </div>

      <Card>
        <div className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium truncate">{task.objective}</h2>
            <Badge className={STATUS_COLORS[task.status] || ""}>{task.status}</Badge>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div><span className="font-medium">ID:</span> {task.id}</div>
            <div><span className="font-medium">Mode:</span> {task.mode}</div>
            <div><span className="font-medium">Repair attempts:</span> {task.repair_attempts} / {task.max_repair_attempts}</div>
            <div><span className="font-medium">Repository:</span> {task.repository_id || "none"}</div>
            {task.error_message && <div className="col-span-2"><span className="font-medium">Error:</span> <span className="text-red-500">{task.error_message}</span></div>}
          </div>

          <div className="flex gap-2 flex-wrap">
            {canExecute && <Button onClick={handleExecute} disabled={executing}>{executing ? "Executing..." : "Execute"}</Button>}
            {canPause && <Button variant="outline" onClick={() => handleAction("pause")}>Pause</Button>}
            {canResume && <Button variant="outline" onClick={() => handleAction("resume")}>Resume</Button>}
            {canCancel && <Button variant="destructive" onClick={() => handleAction("cancel")}>Cancel</Button>}
            {task.status === "completed" && <Button variant="outline" onClick={handleReport}>Generate Report</Button>}
          </div>
        </div>
      </Card>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      {task.progress && task.progress.length > 0 && (
        <Card>
          <div className="p-4 space-y-2">
            <h2 className="text-lg font-medium">Progress</h2>
            {task.progress.map((step: Record<string, any>, i: number) => (
              <div key={i} className="flex items-center gap-2 text-sm border-b pb-1 last:border-0">
                <Badge className={step.status === "completed" ? "bg-green-100 text-green-800" : step.status === "failed" ? "bg-red-100 text-red-800" : "bg-blue-100 text-blue-800"}>
                  {step.status}
                </Badge>
                <span className="font-medium">{step.agent_name}</span>
                <span className="text-muted-foreground truncate flex-1">{step.message}</span>
                <span className="text-xs text-muted-foreground">{step.duration_ms}ms</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {task.analyses && task.analyses.length > 0 && (
        <Card>
          <div className="p-4 space-y-2">
            <h2 className="text-lg font-medium">Failure Analyses</h2>
            {task.analyses.map((a: Record<string, any>, i: number) => (
              <div key={i} className="text-sm border-b pb-1 last:border-0">
                <p><span className="font-medium">Category:</span> {a.category} | <span className="font-medium">Severity:</span> {a.severity}</p>
                <p className="text-muted-foreground">{a.summary}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {report && (
        <Card>
          <div className="p-4 space-y-2">
            <h2 className="text-lg font-medium">Report: {report.title}</h2>
            <p className="text-sm text-muted-foreground">{report.summary}</p>
            {report.sections?.map((section: Record<string, any>, i: number) => (
              <div key={i} className="text-sm border-b pb-1 last:border-0">
                <h3 className="font-medium">{section.title}</h3>
                <p className="text-muted-foreground">{section.content}</p>
              </div>
            ))}
            {report.recommendations?.length > 0 && (
              <div>
                <h3 className="font-medium text-sm">Recommendations</h3>
                <ul className="list-disc pl-5 text-sm">
                  {report.recommendations.map((r: string, i: number) => <li key={i}>{r}</li>)}
                </ul>
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
