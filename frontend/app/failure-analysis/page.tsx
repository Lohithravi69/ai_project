"use client";

import { useState } from "react";
import { v6AnalyzeFailures } from "../../lib/api";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-100 text-red-800",
  high: "bg-orange-100 text-orange-800",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-green-100 text-green-800",
};

export default function FailureAnalysisPage() {
  const [errors, setErrors] = useState("");
  const [results, setResults] = useState<Record<string, any>[]>([]);
  const [loading, setLoading] = useState(false);

  async function handleAnalyze() {
    const errorList = errors.split("\n").filter((e) => e.trim());
    if (errorList.length === 0) return;
    setLoading(true);
    try {
      const data = await v6AnalyzeFailures(errorList);
      setResults(data);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Failure Analysis</h1>
      <p className="text-muted-foreground">Paste error messages to categorize and get recovery strategies.</p>

      <Card>
        <div className="p-4 space-y-3">
          <textarea
            className="w-full border rounded-md p-2 text-sm min-h-[120px] font-mono"
            value={errors}
            onChange={(e) => setErrors(e.currentTarget.value)}
            placeholder={"Paste one error per line...\ne.g.\nModuleNotFoundError: No module named 'xyz'\nSyntaxError: invalid syntax"}
          />
          <Button onClick={handleAnalyze} disabled={loading || !errors.trim()}>
            {loading ? "Analyzing..." : "Analyze"}
          </Button>
        </div>
      </Card>

      {results.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-lg font-medium">Results</h2>
          {results.map((r, i) => (
            <Card key={i}>
              <div className="p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <Badge className={SEVERITY_COLORS[r.severity] || ""}>{r.severity}</Badge>
                  <Badge>{r.category}</Badge>
                </div>
                <p className="text-sm font-mono bg-gray-50 p-2 rounded">{r.summary}</p>
                {r.recovery_strategies?.length > 0 && (
                  <div>
                    <p className="font-medium text-sm">Recovery Strategies:</p>
                    <ul className="list-disc pl-5 text-sm space-y-1">
                      {r.recovery_strategies.map((s: Record<string, any>, j: number) => (
                        <li key={j}>{s.description || s.strategy}</li>
                      ))}
                    </ul>
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
