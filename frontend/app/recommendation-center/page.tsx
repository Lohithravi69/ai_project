"use client";

import { useState, useEffect } from "react";
import { v7ListRecommendations, v7GetRecommendationStats, v7RecommendationAction } from "../../lib/api";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";

const PRI_COLORS: Record<string, string> = {
  high: "bg-red-100 text-red-800",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-green-100 text-green-800",
};

const CAT_COLORS: Record<string, string> = {
  technical_debt: "bg-orange-100 text-orange-800",
  security: "bg-red-100 text-red-800",
  performance: "bg-blue-100 text-blue-800",
  dependencies: "bg-purple-100 text-purple-800",
  architecture: "bg-indigo-100 text-indigo-800",
};

export default function RecommendationCenterPage() {
  const [recommendations, setRecommendations] = useState<Record<string, any>[]>([]);
  const [stats, setStats] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");

  async function load() {
    setLoading(true);
    try {
      const [recs, st] = await Promise.all([
        v7ListRecommendations(filter || undefined),
        v7GetRecommendationStats(),
      ]);
      setRecommendations(Array.isArray(recs) ? recs : []);
      setStats(st);
    } catch {} finally { setLoading(false); }
  }

  useEffect(() => { load(); }, [filter]);

  async function handleAction(id: string, action: "approve" | "dismiss") {
    try {
      await v7RecommendationAction(id, action);
      await load();
    } catch {}
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Recommendation Center</h1>
      <p className="text-muted-foreground">Prioritized recommendations from all analyzers. Approve or dismiss each.</p>

      {stats && (
        <div className="grid grid-cols-4 gap-3">
          <Card><div className="p-3"><p className="text-2xl font-bold">{stats.total}</p><p className="text-xs text-muted-foreground">Total</p></div></Card>
          <Card><div className="p-3"><p className="text-2xl font-bold text-green-600">{stats.approved}</p><p className="text-xs text-muted-foreground">Approved</p></div></Card>
          <Card><div className="p-3"><p className="text-2xl font-bold">{stats.open}</p><p className="text-xs text-muted-foreground">Open</p></div></Card>
          <Card><div className="p-3"><p className="text-2xl font-bold text-gray-400">{stats.dismissed}</p><p className="text-xs text-muted-foreground">Dismissed</p></div></Card>
        </div>
      )}

      <div className="flex gap-2 flex-wrap">
        {["", "technical_debt", "security", "performance", "dependencies", "architecture"].map((cat) => (
          <Badge key={cat} className={`cursor-pointer ${filter === cat ? "ring-2 ring-blue-500" : ""}`} onClick={() => setFilter(cat)}>
            {cat || "All"}
          </Badge>
        ))}
      </div>

      {loading && <p>Loading...</p>}

      <div className="space-y-2">
        {["high", "medium", "low"].map((priority) => {
          const items = recommendations.filter((r) => r.priority === priority);
          if (items.length === 0) return null;
          return (
            <div key={priority}>
              <h2 className={`text-lg font-medium capitalize ${priority === "high" ? "text-red-600" : priority === "medium" ? "text-yellow-600" : "text-green-600"}`}>
                {priority} Priority ({items.length})
              </h2>
              {items.map((r) => (
                <Card key={r.id}>
                  <div className="p-3 space-y-1">
                    <div className="flex items-center gap-2">
                      <Badge className={PRI_COLORS[r.priority] || ""}>{r.priority}</Badge>
                      <Badge className={CAT_COLORS[r.category] || ""}>{r.category}</Badge>
                      <Badge>{r.effort_estimate}</Badge>
                      <Badge className={r.status === "open" ? "bg-blue-100 text-blue-800" : r.status === "approved" ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-800"}>{r.status}</Badge>
                    </div>
                    <p className="font-medium">{r.title}</p>
                    <p className="text-sm text-muted-foreground">{r.description}</p>
                    {r.rationale && <p className="text-xs text-muted-foreground">{r.rationale}</p>}
                    {r.affected_files?.length > 0 && <p className="text-xs text-muted-foreground">Files: {r.affected_files.join(", ")}</p>}
                    {r.status === "open" && (
                      <div className="flex gap-2 mt-1">
                        <Button size="sm" onClick={() => handleAction(r.id, "approve")}>Approve</Button>
                        <Button size="sm" variant="outline" onClick={() => handleAction(r.id, "dismiss")}>Dismiss</Button>
                      </div>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
