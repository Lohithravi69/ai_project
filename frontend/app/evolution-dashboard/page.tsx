"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { v7FullAnalysis, v7GetTrends, v7GetRecommendationStats } from "../../lib/api";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";

export default function EvolutionDashboardPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, any> | null>(null);
  const [files, setFiles] = useState<Record<string, string>>({});
  const [fileName, setFileName] = useState("");
  const [fileContent, setFileContent] = useState("");
  const [reqContent, setReqContent] = useState("");
  const [currentVersion, setCurrentVersion] = useState("v1.0.0");
  const [error, setError] = useState("");

  function addFile() {
    if (!fileName.trim() || !fileContent.trim()) return;
    setFiles((prev) => ({ ...prev, [fileName.trim()]: fileContent }));
    setFileName("");
    setFileContent("");
  }

  function removeFile(name: string) {
    setFiles((prev) => { const n = { ...prev }; delete n[name]; return n; });
  }

  async function handleFullAnalysis() {
    setLoading(true);
    setError("");
    try {
      const data = await v7FullAnalysis({
        files,
        requirements_content: reqContent,
        current_version: currentVersion,
      });
      setResult(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  const COLORS: Record<string, string> = {
    critical: "bg-red-100 text-red-800",
    high: "bg-orange-100 text-orange-800",
    medium: "bg-yellow-100 text-yellow-800",
    low: "bg-green-100 text-green-800",
  };

  const totalIssues = (result?.debt_summary?.total_items || 0) +
    (result?.sec_summary?.total_findings || 0) +
    (result?.perf_summary?.total_findings || 0) +
    (result?.arch_report?.total_changes || 0);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Evolution Engine</h1>
          <p className="text-muted-foreground">Full repository analysis — debt, architecture, deps, performance, security.</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Button variant="outline" size="sm" onClick={() => router.push("/technical-debt")}>Debt</Button>
          <Button variant="outline" size="sm" onClick={() => router.push("/architecture-evolution")}>Architecture</Button>
          <Button variant="outline" size="sm" onClick={() => router.push("/dependency-intelligence")}>Dependencies</Button>
          <Button variant="outline" size="sm" onClick={() => router.push("/performance-advisor")}>Performance</Button>
          <Button variant="outline" size="sm" onClick={() => router.push("/security-advisor")}>Security</Button>
          <Button variant="outline" size="sm" onClick={() => router.push("/version-planner")}>Version Plan</Button>
          <Button variant="outline" size="sm" onClick={() => router.push("/recommendation-center")}>Recommendations</Button>
        </div>
      </div>

      <Card>
        <div className="p-4 space-y-3">
          <h2 className="font-medium">Input Files</h2>
          <div className="flex gap-2">
            <input className="border rounded-md px-3 py-2 text-sm flex-1" value={fileName} onChange={(e) => setFileName(e.currentTarget.value)} placeholder="File path (e.g. src/app.py)" />
            <Button variant="outline" size="sm" onClick={addFile}>Add</Button>
          </div>
          <textarea className="w-full border rounded-md p-2 text-sm min-h-[80px] font-mono" value={fileContent} onChange={(e) => setFileContent(e.currentTarget.value)} placeholder="Paste file content..." />
          {Object.keys(files).length > 0 && (
            <div className="flex flex-wrap gap-1"> {Object.keys(files).map((name) => <Badge key={name} className="cursor-pointer" onClick={() => removeFile(name)}>{name} x</Badge>)} </div>
          )}
          <textarea className="w-full border rounded-md p-2 text-sm min-h-[60px] font-mono" value={reqContent} onChange={(e) => setReqContent(e.currentTarget.value)} placeholder="Paste requirements.txt content (optional)" />
          <div className="flex gap-2 items-center">
            <input className="border rounded-md px-3 py-2 text-sm w-32" value={currentVersion} onChange={(e) => setCurrentVersion(e.currentTarget.value)} placeholder="v1.0.0" />
            <Button onClick={handleFullAnalysis} disabled={loading || Object.keys(files).length === 0}>
              {loading ? "Analyzing..." : "Run Full Analysis"}
            </Button>
          </div>
        </div>
      </Card>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      {result && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Card><div className="p-3"><p className="text-2xl font-bold">{result.debt_summary?.total_items || 0}</p><p className="text-xs text-muted-foreground">Debt Items</p></div></Card>
            <Card><div className="p-3"><p className="text-2xl font-bold">{result.arch_report?.total_changes || 0}</p><p className="text-xs text-muted-foreground">Arch Issues</p></div></Card>
            <Card><div className="p-3"><p className="text-2xl font-bold">{result.sec_summary?.total_findings || 0}</p><p className="text-xs text-muted-foreground">Security Issues</p></div></Card>
            <Card><div className="p-3"><p className="text-2xl font-bold">{result.perf_summary?.total_findings || 0}</p><p className="text-xs text-muted-foreground">Perf Issues</p></div></Card>
          </div>

          {result.version_plan && (
            <Card>
              <div className="p-4 space-y-2">
                <h2 className="text-lg font-medium">Version Plan</h2>
                <p className="text-sm">{result.version_plan.current_version} → <strong>{result.version_plan.suggested_version}</strong> (Effort: {result.version_plan.estimated_effort})</p>
                {result.version_plan.reasons?.map((r: string, i: number) => <p key={i} className="text-sm text-muted-foreground">• {r}</p>)}
              </div>
            </Card>
          )}

          {result.debt_summary?.by_severity && (
            <Card>
              <div className="p-4">
                <h2 className="text-lg font-medium">Debt by Severity</h2>
                <div className="flex gap-2 mt-2">
                  {Object.entries(result.debt_summary.by_severity).map(([sev, count]) => (
                    <Badge key={sev} className={COLORS[sev] || ""}>{sev}: {count as number}</Badge>
                  ))}
                </div>
              </div>
            </Card>
          )}

          {result.sec_summary?.by_severity && (
            <Card>
              <div className="p-4">
                <h2 className="text-lg font-medium">Security by Severity</h2>
                <div className="flex gap-2 mt-2">
                  {Object.entries(result.sec_summary.by_severity).map(([sev, count]) => (
                    <Badge key={sev} className={COLORS[sev] || ""}>{sev}: {count as number}</Badge>
                  ))}
                </div>
              </div>
            </Card>
          )}

          {result.dep_plan && (
            <Card>
              <div className="p-4">
                <h2 className="text-lg font-medium">Dependencies</h2>
                <p className="text-sm">{result.dep_plan.safe_count} safe upgrades, {result.dep_plan.breaking_count} breaking</p>
                <p className="text-xs text-muted-foreground mt-1">{result.dep_plan.recommendation}</p>
              </div>
            </Card>
          )}

          {result.recommendations && (
            <Card>
              <div className="p-4">
                <h2 className="text-lg font-medium">Recommendations</h2>
                {["high", "medium", "low"].map((priority) => {
                  const items = result.recommendations[priority];
                  if (!items?.length) return null;
                  return (
                    <div key={priority} className="mt-2">
                      <h3 className="text-sm font-medium capitalize">{priority} Priority ({items.length})</h3>
                      <ul className="list-disc pl-5 text-sm">
                        {items.slice(0, 5).map((item: Record<string, any>, i: number) => (
                          <li key={i}>{item.title}</li>
                        ))}
                      </ul>
                    </div>
                  );
                })}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
