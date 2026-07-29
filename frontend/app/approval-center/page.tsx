"use client";

import { useEffect, useState } from "react";
import { v4ListApprovalRequests, v4ApproveRequest, v4RejectRequest } from "../../lib/api";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Badge } from "../../components/ui/badge";

export default function ApprovalCenterPage() {
  const [requests, setRequests] = useState<Array<Record<string, any>>>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const data = await v4ListApprovalRequests();
      setRequests(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleApprove(id: string) {
    setActionLoading(id);
    try {
      await v4ApproveRequest(id);
      await load();
    } catch (err) {
      console.error(err);
    } finally {
      setActionLoading(null);
    }
  }

  async function handleReject(id: string) {
    const reason = prompt("Rejection reason (optional):");
    setActionLoading(id);
    try {
      await v4RejectRequest(id, reason || "");
      await load();
    } catch (err) {
      console.error(err);
    } finally {
      setActionLoading(null);
    }
  }

  if (loading) return <div className="p-6">Loading approval requests...</div>;

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Approval Center</h1>
      <p className="text-muted-foreground">{requests.length} requests</p>
      {requests.length === 0 && <p className="text-sm text-muted-foreground">No pending approval requests.</p>}
      <div className="space-y-3">
        {requests.map((req) => (
          <Card key={req.id}>
            <div className="p-4 space-y-2">
              <div className="flex items-center justify-between">
                <h2 className="font-medium">Plan: {req.plan_id?.slice(0, 8)}...</h2>
                <Badge variant={req.status === "pending" ? "outline" : req.status === "approved" ? "default" : "destructive"}>{req.status}</Badge>
              </div>
              {req.explanation && <p className="text-sm">{req.explanation}</p>}
              {req.diff_preview && (
                <pre className="text-xs bg-muted p-2 rounded overflow-x-auto max-h-40">{req.diff_preview}</pre>
              )}
              {req.status === "pending" && (
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => handleApprove(req.id)} disabled={actionLoading === req.id}>Approve</Button>
                  <Button size="sm" variant="destructive" onClick={() => handleReject(req.id)} disabled={actionLoading === req.id}>Reject</Button>
                </div>
              )}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
