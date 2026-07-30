"use client";

import { useState } from "react";
import { v7AnalyzeSecurity } from "../../lib/api";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";

const SEV_COLORS: Record<string, string> = {
  critical: "bg-red-100 text-red-800",
  high: "bg-orange-100 text-orange-800",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-green-100 text-green-800",
};

export default function SecurityAdvisorPage() {
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
    try { setResult(await v7AnalyzeSecurity(files)); } catch {} finally { setLoading(false); }
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Security Advisor</h1>
      <p className="text-muted-foreground">Find secrets in code, unsafe execution, SQL injection, XSS, and more.</p>
      <Card>
        <div className="p-4 space-y-3">
          <div className="flex gap-2">
            <input className="border rounded-md px-3 py-2 text-sm flex-1" value={fileName} onChange={e => setFileName(e.currentTarget.value)} placeholder="File path" />
            <Button variant="outline" onClick={addFile}>Add</Button>
          </div>
          <textarea className="w-full border rounded-md p-2 text-sm min-h-[80px] font-mono" value={fileContent} onChange={e => setFileContent(e.currentTarget.value)} placeholder="Paste file content..." />
          {Object.keys(files).length > 0 && <div className="flex flex-wrap gap-1">{Object.keys(files).map(n => <Badge key={n} className="cursor-pointer" onClick={() => removeFile(n)}>{n} x</Badge>)}</div>}
          <Button onClick={handleAnalyze} disabled={loading || Object.keys(files).length === 0}>{loading ? "Analyzing..." : "Analyze Security"}</Button>
        </div>
      </Card>

      {result && (
        <>
          <Card><div className="p-4"><h2 className="text-lg font-medium">Risk Score: {result.summary?.risk_score?.toFixed(1) || "?"}/10</h2><div className="flex gap-2 mt-2">{Object.entries(result.summary?.by_severity || {}).map(([s, c]) => <Badge key={s} className={SEV_COLORS[s] || ""}>{s}: {c as number}</Badge>)}</div></div></Card>
          {result.findings?.map((f: Record<string, any>, i: number) => (
            <Card key={i}><div className="p-3 space-y-1">
              <div className="flex items-center gap-2"><Badge className={SEV_COLORS[f.severity] || ""}>{f.severity}</Badge><Badge>{f.finding_type}</Badge>{f.cwe && <span className="text-xs text-muted-foreground">{f.cwe}</span>}</div>
              <p className="text-sm">{f.description}</p>
              <p className="text-xs text-muted-foreground">{f.file_path}:{f.line_number}</p>
              <p className="text-xs text-blue-600">{f.suggestion}</p>
            </div></Card>
          ))}
        </>
      )}
    </div>
  );
}
