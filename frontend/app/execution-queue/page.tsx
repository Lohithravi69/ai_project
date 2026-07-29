"use client";

import { useEffect, useState } from "react";
import { v4ListPlans } from "../../lib/api";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";

const statusColor: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  pending: "outline",
  approved: "default",
  rejected: "destructive",
  executed: "secondary",
};

export default function ExecutionQueuePage() {
  const [plans, setPlans] = useState<Array<Record<string, any>>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    v4ListPlans()
      .then(setPlans)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6">Loading execution queue...</div>;

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Execution Queue</h1>
      <p className="text-muted-foreground">{plans.length} plans</p>
      {plans.length === 0 && <p className="text-sm text-muted-foreground">No plans yet. Create one in the Execution Planner.</p>}
      <div className="space-y-3">
        {plans.map((plan) => (
          <Card key={plan.id}>
            <div className="p-4">
              <div className="flex items-center justify-between mb-2">
                <h2 className="font-medium">{plan.objective}</h2>
                <Badge variant={statusColor[plan.approval_status] || "outline"}>{plan.approval_status}</Badge>
              </div>
              <p className="text-sm text-muted-foreground mb-1">{plan.reasoning}</p>
              <div className="flex gap-3 text-xs text-muted-foreground">
                <span>Risk: {plan.risk_score}</span>
                <span>Duration: {Math.round(plan.estimated_duration_ms / 1000)}s</span>
                <span>Tools: {(plan.required_tools || []).length}</span>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
