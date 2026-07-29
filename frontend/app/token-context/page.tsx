"use client";

import { useEffect, useState } from "react";
import { getUsageObservability } from "../../lib/api";

export default function TokenContextPage() {
  const [data, setData] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const response = await getUsageObservability();
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
        <h1 className="text-2xl font-semibold">Token & Context Dashboard</h1>
        <button className="btn-primary" onClick={load} disabled={loading}>{loading ? "Refreshing…" : "Refresh"}</button>
      </div>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {[
          ["Prompt tokens", data?.total_prompt_tokens ?? 0],
          ["Completion tokens", data?.total_completion_tokens ?? 0],
          ["Recent queries", data?.recent_queries ?? 0],
          ["Average context size", data?.avg_context_size ?? 0],
          ["Average retrieved chunks", data?.avg_retrieved_chunks ?? 0],
          ["Average response time (ms)", data?.avg_response_time_ms ?? 0],
        ].map(([label, value]) => (
          <div key={String(label)} className="rounded-lg border p-4">
            <p className="text-sm text-gray-500">{String(label)}</p>
            <p className="mt-2 text-3xl font-semibold">{String(value)}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
