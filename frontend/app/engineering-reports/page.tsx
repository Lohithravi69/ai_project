"use client";

import { useState, useEffect } from "react";
import { v6ListReports } from "../../lib/api";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";

export default function EngineeringReportsPage() {
  const [reports, setReports] = useState<Record<string, any>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    v6ListReports(50)
      .then((data) => setReports(Array.isArray(data) ? data : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Engineering Reports</h1>
      <p className="text-muted-foreground">Generated reports from autonomous task executions.</p>

      {loading && <p>Loading...</p>}
      {!loading && reports.length === 0 && <p className="text-muted-foreground">No reports generated yet.</p>}

      <div className="space-y-2">
        {reports.map((r, i) => (
          <Card key={r.id || i}>
            <div className="p-4 space-y-2">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-medium">{r.title}</h2>
                <Badge>{r.report_type}</Badge>
              </div>
              <p className="text-sm text-muted-foreground">{r.summary}</p>
              {r.sections?.length > 0 && (
                <div className="text-sm space-y-1">
                  <p className="font-medium">Sections ({r.sections.length})</p>
                  <ul className="list-disc pl-5">
                    {r.sections.map((s: Record<string, any>, j: number) => (
                      <li key={j}>{s.title} - {s.type}</li>
                    ))}
                  </ul>
                </div>
              )}
              {r.recommendations?.length > 0 && (
                <div className="text-sm">
                  <p className="font-medium">Recommendations:</p>
                  <ul className="list-disc pl-5">
                    {r.recommendations.map((rec: string, j: number) => (
                      <li key={j}>{rec}</li>
                    ))}
                  </ul>
                </div>
              )}
              {r.metrics && Object.keys(r.metrics).length > 0 && (
                <div className="text-xs text-muted-foreground">
                  Metrics: {JSON.stringify(r.metrics)}
                </div>
              )}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
