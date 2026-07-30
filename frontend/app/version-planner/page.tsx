"use client";

import { useState } from "react";
import { v7PlanVersion } from "../../lib/api";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";

export default function VersionPlannerPage() {
  const [currentVersion, setCurrentVersion] = useState("v1.0.0");
  const [debtItems, setDebtItems] = useState(0);
  const [archIssues, setArchIssues] = useState(0);
  const [secIssues, setSecIssues] = useState(0);
  const [perfIssues, setPerfIssues] = useState(0);
  const [breakingDeps, setBreakingDeps] = useState(0);
  const [result, setResult] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);

  async function handlePlan() {
    setLoading(true);
    try {
      const payload: Record<string, any> = { current_version: currentVersion };
      if (debtItems > 0) payload.debt_summary = { total_items: debtItems };
      if (archIssues > 0) payload.arch_changes = Array.from({ length: archIssues }, () => ({ change_type: "srp_violation", severity: "high" }));
      if (secIssues > 0) payload.sec_findings = Array.from({ length: secIssues }, () => ({ severity: "high" }));
      if (perfIssues > 0) payload.perf_findings = Array.from({ length: perfIssues }, () => ({ severity: "medium" }));
      if (breakingDeps > 0) payload.dep_recs = Array.from({ length: breakingDeps }, () => ({ breaking: true, category: "outdated" }));
      setResult(await v7PlanVersion(payload));
    } catch {} finally { setLoading(false); }
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Version Evolution Planner</h1>
      <p className="text-muted-foreground">Plan your next version based on analysis findings.</p>

      <Card>
        <div className="p-4 space-y-3">
          <label className="text-sm font-medium">Current Version <input className="border rounded-md px-3 py-2 text-sm w-32 ml-2" value={currentVersion} onChange={e => setCurrentVersion(e.currentTarget.value)} /></label>
          <div className="grid grid-cols-2 gap-3">
            <label className="text-sm">Debt Items <input type="number" min="0" className="border rounded-md px-3 py-2 text-sm w-20 ml-2" value={debtItems} onChange={e => setDebtItems(parseInt(e.currentTarget.value) || 0)} /></label>
            <label className="text-sm">Arch Issues <input type="number" min="0" className="border rounded-md px-3 py-2 text-sm w-20 ml-2" value={archIssues} onChange={e => setArchIssues(parseInt(e.currentTarget.value) || 0)} /></label>
            <label className="text-sm">Security Issues <input type="number" min="0" className="border rounded-md px-3 py-2 text-sm w-20 ml-2" value={secIssues} onChange={e => setSecIssues(parseInt(e.currentTarget.value) || 0)} /></label>
            <label className="text-sm">Perf Issues <input type="number" min="0" className="border rounded-md px-3 py-2 text-sm w-20 ml-2" value={perfIssues} onChange={e => setPerfIssues(parseInt(e.currentTarget.value) || 0)} /></label>
            <label className="text-sm">Breaking Deps <input type="number" min="0" className="border rounded-md px-3 py-2 text-sm w-20 ml-2" value={breakingDeps} onChange={e => setBreakingDeps(parseInt(e.currentTarget.value) || 0)} /></label>
          </div>
          <Button onClick={handlePlan} disabled={loading}>{loading ? "Planning..." : "Generate Version Plan"}</Button>
        </div>
      </Card>

      {result && (
        <Card>
          <div className="p-4 space-y-3">
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-bold">{result.current_version}</h2>
              <span className="text-xl">→</span>
              <h2 className="text-2xl font-bold text-green-600">{result.suggested_version}</h2>
              <Badge>Effort: {result.estimated_effort}</Badge>
            </div>
            <p className="text-sm whitespace-pre-line">{result.summary}</p>
            {result.reasons?.length > 0 && <div><h3 className="font-medium">Reasons</h3><ul className="list-disc pl-5 text-sm">{result.reasons.map((r: string, i: number) => <li key={i}>{r}</li>)}</ul></div>}
            {result.changes?.length > 0 && <div><h3 className="font-medium">Changes</h3><ul className="list-disc pl-5 text-sm">{result.changes.map((c: Record<string, any>, i: number) => <li key={i}>{c.description} ({c.category})</li>)}</ul></div>}
            {result.risks?.length > 0 && <div><h3 className="font-medium text-red-600">Risks</h3><ul className="list-disc pl-5 text-sm">{result.risks.map((r: string, i: number) => <li key={i}>{r}</li>)}</ul></div>}
          </div>
        </Card>
      )}
    </div>
  );
}
