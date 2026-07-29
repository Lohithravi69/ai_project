"use client";

import { useEffect, useState } from "react";
import { getAgentObservability } from "../../lib/api";

export default function AgentTimelinePage() {
  const [data, setData] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const response = await getAgentObservability();
      setData(response);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="space-y-4 p-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Agent Execution Timeline</h1>
        <button className="btn-primary" onClick={load} disabled={loading}>{loading ? "Refreshing…" : "Refresh"}</button>
      </div>

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-lg border p-4">
          <h2 className="font-medium">Current State</h2>
          <p className="mt-2 text-sm text-gray-700">{data?.executions?.[0]?.status ?? "No executions yet"}</p>
          <p className="mt-1 text-xs text-gray-500">Latest task: {data?.executions?.[0]?.task_name ?? "-"}</p>
        </div>
        <div className="rounded-lg border p-4">
          <h2 className="font-medium">Task Queue</h2>
          <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-xs text-gray-700">{JSON.stringify(data?.task_queue ?? {}, null, 2)}</pre>
        </div>
        <div className="rounded-lg border p-4">
          <h2 className="font-medium">Execution Summary</h2>
          <p className="mt-2 text-sm text-gray-700">Total executions: {data?.executions?.length ?? 0}</p>
        </div>
      </section>

      <section className="rounded-lg border p-4">
        <h2 className="font-medium">History</h2>
        <div className="mt-3 space-y-3">
          {(data?.executions ?? []).map((execution: Record<string, any>) => (
            <div key={execution.id} className="rounded border bg-white p-3 text-sm">
              <div className="flex flex-wrap justify-between gap-2">
                <div>
                  <p className="font-medium">{execution.agent_name} / {execution.task_name}</p>
                  <p className="text-xs text-gray-500">Repository: {execution.repository_id ?? "-"}</p>
                </div>
                <div className="text-right text-xs text-gray-500">
                  <p>Status: {execution.status}</p>
                  <p>Duration: {execution.duration_ms ?? 0} ms</p>
                </div>
              </div>
              <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs">{JSON.stringify(execution.step_logs ?? [], null, 2)}</pre>
              {execution.error_message ? <p className="mt-2 text-xs text-red-600">{execution.error_message}</p> : null}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
