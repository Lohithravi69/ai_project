"use client";

import { useState } from "react";
import { v7AnalyzeArchitecture } from "../../lib/api";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";

const PRI_COLORS: Record<string, string> = {
  "Single Responsibility": "bg-red-100 text-red-800",
  "Open/Closed": "bg-orange-100 text-orange-800",
  "Layered Architecture": "bg-purple-100 text-purple-800",
  "Dependency Inversion": "bg-blue-100 text-blue-800",
};

export default function ArchitectureEvolutionPage() {
  const [files, setFiles] = useState<Record<string, string>>({});
  const [fileName, setFileName] = useState("");
  const [fileContent, setFileContent] = useState("");
  const [result, setResult] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);

  function addFile() {
    if (!fileName.trim() || !fileContent.trim()) return;
    setFiles(p => ({ ...p, [fileName.trim()]: fileContent }));
    setFileName(""); setFileContent("");
  }
  function removeFile(n: string) { setFiles(p => { const x = { ...p }; delete x[n]; return x; }); }

  async function handleAnalyze() {
    setLoading(true);
    try { setResult(await v7AnalyzeArchitecture(files)); } catch {} finally { setLoading(false); }
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Architecture Evolution Engine</h1>
      <p className="text-muted-foreground">Detect SOLID violations, layer separation issues, and coupling problems.</p>
      <Card>
        <div className="p-4 space-y-3">
          <div className="flex gap-2">
            <input className="border rounded-md px-3 py-2 text-sm flex-1" value={fileName} onChange={e => setFileName(e.currentTarget.value)} placeholder="File path" />
            <Button variant="outline" onClick={addFile}>Add</Button>
          </div>
          <textarea className="w-full border rounded-md p-2 text-sm min-h-[80px] font-mono" value={fileContent} onChange={e => setFileContent(e.currentTarget.value)} placeholder="Paste file content..." />
          {Object.keys(files).length > 0 && <div className="flex flex-wrap gap-1">{Object.keys(files).map(n => <Badge key={n} className="cursor-pointer" onClick={() => removeFile(n)}>{n} x</Badge>)}</div>}
          <Button onClick={handleAnalyze} disabled={loading || Object.keys(files).length === 0}>{loading ? "Analyzing..." : "Analyze Architecture"}</Button>
        </div>
      </Card>

      {result && (
        <>
          <div className="grid grid-cols-3 gap-3">
            <Card><div className="p-3"><p className="text-2xl font-bold">{result.report?.srp_violations || 0}</p><p className="text-xs text-muted-foreground">SRP Violations</p></div></Card>
            <Card><div className="p-3"><p className="text-2xl font-bold">{result.report?.ocp_violations || 0}</p><p className="text-xs text-muted-foreground">OCP Violations</p></div></Card>
            <Card><div className="p-3"><p className="text-2xl font-bold">{result.report?.layer_violations || 0}</p><p className="text-xs text-muted-foreground">Layer Violations</p></div></Card>
          </div>
          {result.changes?.map((c: Record<string, any>, i: number) => (
            <Card key={i}><div className="p-3 space-y-1">
              <div className="flex items-center gap-2"><Badge className={PRI_COLORS[c.principle] || ""}>{c.principle}</Badge><Badge>{c.change_type}</Badge></div>
              <p className="text-sm">{c.description}</p>
              <p className="text-xs text-muted-foreground">{c.rationale}</p>
              <p className="text-xs text-blue-600">Confidence: {(c.confidence * 100).toFixed(0)}%</p>
            </div></Card>
          ))}
        </>
      )}
    </div>
  );
}
