"use client";

import { useState } from "react";
import { v4DryRunTool } from "../../lib/api";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";

export default function DiffViewerPage() {
  const [toolName, setToolName] = useState("WriteFile");
  const [path, setPath] = useState("");
  const [content, setContent] = useState("");
  const [repoId, setRepoId] = useState("");
  const [result, setResult] = useState<Record<string, any> | null>(null);
  const [loading, setLoading] = useState(false);

  async function handlePreview() {
    setLoading(true);
    try {
      const res = await v4DryRunTool({
        tool_name: toolName,
        inputs: {
          repository_id: repoId,
          path,
          content: toolName === "WriteFile" ? content : undefined,
        },
      });
      setResult(res);
    } catch (err) {
      console.error(err);
      setResult({ error: String(err) });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Diff Viewer</h1>
      <p className="text-muted-foreground">Preview changes before execution.</p>
      <Card>
        <div className="p-4 space-y-3">
          <div className="flex gap-2">
            <Input value={repoId} onChange={(e) => setRepoId(e.currentTarget.value)} placeholder="Repository ID" className="flex-1" />
            <select className="border rounded-md px-2 text-sm" value={toolName} onChange={(e) => setToolName(e.currentTarget.value)}>
              <option value="WriteFile">WriteFile</option>
              <option value="CreateFile">CreateFile</option>
              <option value="DeleteFile">DeleteFile</option>
              <option value="MoveFile">MoveFile</option>
            </select>
          </div>
          <Input value={path} onChange={(e) => setPath(e.currentTarget.value)} placeholder="File path (e.g. src/app.py)" />
          {toolName === "WriteFile" && (
            <textarea
              className="w-full border rounded-md p-2 text-sm min-h-[120px] font-mono"
              value={content} onChange={(e) => setContent(e.currentTarget.value)}
              placeholder="New file content..."
            />
          )}
          <Button onClick={handlePreview} disabled={loading || !repoId || !path}>
            {loading ? "Generating..." : "Preview Diff"}
          </Button>
        </div>
      </Card>
      {result && (
        <Card>
          <div className="p-4 space-y-2">
            <h2 className="font-medium">Diff Preview</h2>
            {result.diff_preview && (
              <pre className="text-xs bg-muted p-3 rounded overflow-x-auto max-h-96 whitespace-pre-wrap">{result.diff_preview}</pre>
            )}
            <div className="flex gap-3 text-xs text-muted-foreground">
              <span>Impact: {result.estimated_impact}</span>
              {result.affected_files && <span>Files: {result.affected_files.join(", ")}</span>}
              {result.risks?.length > 0 && <span>Risks: {result.risks.join(", ")}</span>}
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
