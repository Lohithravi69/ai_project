"use client";

import { useState } from "react";
import { v7AnalyzeDependencies } from "../../lib/api";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";

export default function DependencyIntelligencePage() {
  const [content, setContent] = useState("");
  const [result, setResult] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleAnalyze() {
    setLoading(true);
    try { setResult(await v7AnalyzeDependencies(content)); } catch {} finally { setLoading(false); }
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Dependency Intelligence</h1>
      <p className="text-muted-foreground">Analyze requirements for outdated packages, breaking changes, and upgrade paths.</p>
      <Card>
        <div className="p-4 space-y-3">
          <textarea className="w-full border rounded-md p-2 text-sm min-h-[150px] font-mono" value={content} onChange={e => setContent(e.currentTarget.value)} placeholder={"Paste requirements.txt content...\ne.g.\nfastapi==0.100.0\nuvicorn==0.20.0\nsqlalchemy==1.4.0"} />
          <Button onClick={handleAnalyze} disabled={loading || !content.trim()}>{loading ? "Analyzing..." : "Analyze Dependencies"}</Button>
        </div>
      </Card>

      {result && (
        <>
          {result.upgrade_plan && (
            <Card><div className="p-4"><h2 className="text-lg font-medium">Upgrade Plan</h2><p className="text-sm">{result.upgrade_plan.safe_count} safe upgrades, {result.upgrade_plan.breaking_count} breaking</p><p className="text-xs text-muted-foreground">{result.upgrade_plan.recommendation}</p></div></Card>
          )}
          {result.recommendations?.map((r: Record<string, any>, i: number) => (
            <Card key={i}><div className="p-3 space-y-1">
              <div className="flex items-center gap-2">
                <Badge className={r.severity === "high" ? "bg-red-100 text-red-800" : r.severity === "medium" ? "bg-yellow-100 text-yellow-800" : "bg-green-100 text-green-800"}>{r.severity}</Badge>
                <Badge>{r.category}</Badge>
                {r.breaking && <Badge className="bg-purple-100 text-purple-800">breaking</Badge>}
              </div>
              <p className="font-medium">{r.package}</p>
              <p className="text-sm">{r.current_version} → <strong>{r.suggested_version}</strong></p>
              <p className="text-xs text-muted-foreground">{r.description}</p>
              <p className="text-xs text-blue-600">{r.upgrade_path}</p>
            </div></Card>
          ))}
        </>
      )}
    </div>
  );
}
