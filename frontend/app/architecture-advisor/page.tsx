"use client";

import { useState } from "react";
import { v6AnalyzeArchitecture } from "../../lib/api";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";

const CATEGORY_COLORS: Record<string, string> = {
  security: "bg-red-100 text-red-800",
  layering: "bg-purple-100 text-purple-800",
  dependency: "bg-orange-100 text-orange-800",
  error_handling: "bg-yellow-100 text-yellow-800",
  maintainability: "bg-blue-100 text-blue-800",
  design: "bg-indigo-100 text-indigo-800",
  api: "bg-cyan-100 text-cyan-800",
  import: "bg-gray-100 text-gray-800",
  completeness: "bg-green-100 text-green-800",
};

export default function ArchitectureAdvisorPage() {
  const [files, setFiles] = useState<Record<string, string>>({});
  const [fileName, setFileName] = useState("");
  const [fileContent, setFileContent] = useState("");
  const [results, setResults] = useState<Record<string, any>[]>([]);
  const [loading, setLoading] = useState(false);

  function addFile() {
    if (!fileName.trim() || !fileContent.trim()) return;
    setFiles((prev) => ({ ...prev, [fileName.trim()]: fileContent }));
    setFileName("");
    setFileContent("");
  }

  function removeFile(name: string) {
    setFiles((prev) => {
      const next = { ...prev };
      delete next[name];
      return next;
    });
  }

  async function handleAnalyze() {
    if (Object.keys(files).length === 0) return;
    setLoading(true);
    try {
      const data = await v6AnalyzeArchitecture(files);
      setResults(data);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Architecture Advisor</h1>
      <p className="text-muted-foreground">Analyze code files for architectural improvements.</p>

      <Card>
        <div className="p-4 space-y-3">
          <div className="flex gap-2">
            <input
              className="border rounded-md px-3 py-2 text-sm flex-1"
              value={fileName}
              onChange={(e) => setFileName(e.currentTarget.value)}
              placeholder="File path (e.g. src/app.py)"
            />
            <Button variant="outline" onClick={addFile} disabled={!fileName.trim() || !fileContent.trim()}>Add</Button>
          </div>
          <textarea
            className="w-full border rounded-md p-2 text-sm min-h-[100px] font-mono"
            value={fileContent}
            onChange={(e) => setFileContent(e.currentTarget.value)}
            placeholder="Paste file content here..."
          />
          {Object.keys(files).length > 0 && (
            <div className="flex flex-wrap gap-1">
              {Object.keys(files).map((name) => (
                <Badge key={name} className="cursor-pointer" onClick={() => removeFile(name)}>
                  {name} x
                </Badge>
              ))}
            </div>
          )}
          <Button onClick={handleAnalyze} disabled={loading || Object.keys(files).length === 0}>
            {loading ? "Analyzing..." : "Analyze Architecture"}
          </Button>
        </div>
      </Card>

      {results.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-lg font-medium">Recommendations ({results.length})</h2>
          {results.map((r, i) => (
            <Card key={i}>
              <div className="p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <Badge className={CATEGORY_COLORS[r.category] || ""}>{r.category}</Badge>
                  <span className="text-xs text-muted-foreground">Confidence: {(r.confidence * 100).toFixed(0)}%</span>
                </div>
                <p className="font-medium">{r.title}</p>
                <p className="text-sm text-muted-foreground">{r.description}</p>
                {r.affected_files?.length > 0 && (
                  <div className="text-xs text-muted-foreground">
                    Files: {r.affected_files.join(", ")}
                  </div>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
