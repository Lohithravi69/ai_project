"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { v7GetBrief, v6ListExperiences, fetchRepositories } from "../../lib/api";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";

const DIR_COLORS: Record<string, string> = {
  up: "text-green-500",
  down: "text-red-500",
  stable: "text-gray-400",
};

export default function PortfolioDashboardPage() {
  const router = useRouter();
  const [brief, setBrief] = useState<Record<string, any> | null>(null);
  const [experiences, setExperiences] = useState<Record<string, any>[]>([]);
  const [repos, setRepos] = useState<Record<string, any>[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const [b, exp] = await Promise.all([
        v7GetBrief(),
        v6ListExperiences(10),
      ]);
      setBrief(b);
      setExperiences(Array.isArray(exp) ? exp : []);
      try {
        const r = await fetchRepositories();
        setRepos(Array.isArray(r) ? r : []);
      } catch {}
    } catch {} finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  const recs = brief?.recommendations || {};
  const healthPct = brief ? Math.round((brief.health_score || 0) * 100) : 0;

  if (loading) return <div className="p-6"><p>Loading...</p></div>;

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Portfolio Dashboard</h1>
          <p className="text-muted-foreground">Daily engineering overview — health, repositories, tasks, experiences.</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Button variant="outline" size="sm" onClick={() => router.push("/evolution-dashboard")}>Evolution</Button>
          <Button variant="outline" size="sm" onClick={() => router.push("/recommendation-center")}>Recommendations</Button>
          <Button variant="outline" size="sm" onClick={() => router.push("/autonomous")}>Tasks</Button>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3">
        <Card>
          <div className="p-3">
            <p className={`text-3xl font-bold ${healthPct > 70 ? "text-green-500" : healthPct > 40 ? "text-yellow-500" : "text-red-500"}`}>
              {healthPct}%
            </p>
            <p className="text-xs text-muted-foreground">Portfolio Health</p>
          </div>
        </Card>
        <Card>
          <div className="p-3">
            <p className="text-3xl font-bold">{recs.open || 0}</p>
            <p className="text-xs text-muted-foreground">Open Recommendations</p>
          </div>
        </Card>
        <Card>
          <div className="p-3">
            <p className="text-3xl font-bold">{repos.length}</p>
            <p className="text-xs text-muted-foreground">Repositories</p>
          </div>
        </Card>
        <Card>
          <div className="p-3">
            <p className="text-3xl font-bold">{brief?.experience_count || 0}</p>
            <p className="text-xs text-muted-foreground">Experiences</p>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Card>
          <div className="p-4">
            <h2 className="text-lg font-semibold mb-2">Trends</h2>
            <p className="flex gap-3 text-sm">
              <span>Improving: <strong className="text-green-500">{brief?.improving || 0}</strong></span>
              <span>Declining: <strong className="text-red-500">{brief?.declining || 0}</strong></span>
              <span>Stable: <strong>{brief?.stable || 0}</strong></span>
            </p>
            <div className="mt-3 space-y-1">
              {(brief?.metrics || []).map((m: any, i: number) => (
                <div key={i} className="flex justify-between text-sm">
                  <span>{m.name}</span>
                  <span className={DIR_COLORS[m.direction] || ""}>
                    {m.current_value}{m.unit} {m.direction === "up" ? "↑" : m.direction === "down" ? "↓" : "→"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </Card>

        <Card>
          <div className="p-4">
            <h2 className="text-lg font-semibold mb-2">Repositories</h2>
            {repos.length === 0 ? <p className="text-sm text-muted-foreground">No repositories registered.</p> : (
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {repos.map((r: any) => (
                  <div key={r.id} className="flex justify-between text-sm">
                    <span>{r.full_name}</span>
                    <Badge>{r.language_summary?.primary_language || "?"}</Badge>
                  </div>
                ))}
              </div>
            )}
            <Button variant="outline" size="sm" className="mt-2" onClick={() => router.push("/workspace-manager")}>
              Manage Repos
            </Button>
          </div>
        </Card>
      </div>

      <Card>
        <div className="p-4">
          <h2 className="text-lg font-semibold mb-2">Recent Experiences</h2>
          {experiences.length === 0 ? <p className="text-sm text-muted-foreground">No experiences recorded yet.</p> : (
            <div className="space-y-2">
              {experiences.map((e: any) => (
                <div key={e.id} className="flex items-center justify-between text-sm border-b pb-1">
                  <span className="truncate max-w-md">{e.objective}</span>
                  <div className="flex gap-2 items-center shrink-0">
                    <Badge>{e.outcome || "unknown"}</Badge>
                    {e.duration_ms > 0 && <span className="text-xs text-muted-foreground">{e.duration_ms}ms</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>

      <div className="flex gap-2 flex-wrap">
        <Button variant="outline" size="sm" onClick={() => router.push("/system-health")}>System Health</Button>
        <Button variant="outline" size="sm" onClick={() => router.push("/project-health")}>Project Health</Button>
        <Button variant="outline" size="sm" onClick={() => router.push("/engineering-reports")}>Reports</Button>
        <Button variant="outline" size="sm" onClick={() => router.push("/pattern-library")}>Patterns</Button>
        <Button variant="outline" size="sm" onClick={() => router.push("/execution-logs")}>Logs</Button>
      </div>
    </div>
  );
}
