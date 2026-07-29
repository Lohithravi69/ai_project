"use client";

import { useEffect, useState } from "react";
import { getSystemHealth } from "../../lib/api";

export default function SystemHealthPage() {
  const [data, setData] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const response = await getSystemHealth();
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
        <h1 className="text-2xl font-semibold">AI System Health</h1>
        <button className="btn-primary" onClick={load} disabled={loading}>{loading ? "Refreshing…" : "Refresh"}</button>
      </div>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {data?.dependencies?.map((dep: Record<string, any>) => (
          <div key={String(dep.name)} className="rounded-lg border p-4">
            <p className="text-sm text-gray-500">{String(dep.name)}</p>
            <p className="mt-2 text-xl font-semibold">{String(dep.status)}</p>
            <p className="mt-1 text-xs text-gray-500 break-words">{String(dep.detail ?? "")}</p>
          </div>
        ))}
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border p-4">
          <h2 className="font-medium">Workers</h2>
          <pre className="mt-2 max-h-[24rem] overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-3 text-xs">{JSON.stringify(data?.workers ?? {}, null, 2)}</pre>
        </div>
        <div className="rounded-lg border p-4">
          <h2 className="font-medium">Resources</h2>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {Object.entries(data?.resources ?? {}).map(([label, value]) => (
              <div key={label} className="rounded border bg-white p-3">
                <p className="text-xs text-gray-500">{label}</p>
                <p className="mt-1 text-lg font-semibold">{String(value ?? "-")}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
