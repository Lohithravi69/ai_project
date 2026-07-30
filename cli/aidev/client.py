from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

CONFIG_DIR = Path.home() / ".config" / "aidev"
CONFIG_FILE = CONFIG_DIR / "config.json"


class AIClient:
    def __init__(self, base_url: str = "") -> None:
        config = self._load_config()
        self.base_url = (base_url or config.get("backend_url", "http://localhost:8000")).rstrip("/")
        self._token = config.get("token", "")
        self._client = httpx.Client(timeout=120.0, headers=self._headers())

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Content-Type": "application/json"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    @staticmethod
    def _load_config() -> dict[str, Any]:
        if CONFIG_FILE.exists():
            try:
                return json.loads(CONFIG_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    @staticmethod
    def save_config(**kwargs: Any) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        config = AIClient._load_config()
        config.update(kwargs)
        CONFIG_FILE.write_text(json.dumps(config, indent=2))

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        r = self._client.request(method, url, **kwargs)
        if r.status_code == 422:
            raise ValueError(f"Validation error: {r.text}")
        if r.status_code == 404:
            raise ValueError(f"Not found: {path}")
        r.raise_for_status()
        return r.json()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("GET", path, params=params)

    def _post(self, path: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("POST", path, json=json_data or {})

    # ── Repos ────────────────────────────────────────────────────────────────

    def list_repos(self) -> list[dict[str, Any]]:
        data = self._get("/api/repositories")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("repositories", data.get("items", []))
        return []

    # ── Plans ────────────────────────────────────────────────────────────────

    def create_plan(self, objective: str, request_text: str = "", repo_id: str = "") -> dict[str, Any]:
        return self._post("/api/v4/plan", {
            "objective": objective,
            "request_text": request_text or objective,
            "repository_ids": [repo_id] if repo_id else [],
        })

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        return self._get(f"/api/v4/plan/{plan_id}")

    def list_plans(self, limit: int = 20) -> list[dict[str, Any]]:
        data = self._get("/api/v4/plans", {"limit": limit})
        return data if isinstance(data, list) else []

    # ── Execute ──────────────────────────────────────────────────────────────

    def run_agents(self, request_text: str, repo_id: str = "", mode: str = "full") -> dict[str, Any]:
        return self._post("/api/v5/agents/run", {
            "request_text": request_text,
            "repository_id": repo_id,
            "mode": mode,
        })

    def get_execution_status(self, execution_id: str) -> dict[str, Any]:
        return self._get(f"/api/v5/agents/{execution_id}/status")

    def get_trace(self, plan_id: str) -> list[dict[str, Any]]:
        data = self._get(f"/api/v5/agents/{plan_id}/trace")
        return data if isinstance(data, list) else []

    # ── Autonomous Tasks ────────────────────────────────────────────────────

    def create_task(self, objective: str, repo_id: str = "", mode: str = "full") -> dict[str, Any]:
        return self._post("/api/v6/tasks", {
            "objective": objective,
            "repository_id": repo_id,
            "mode": mode,
        })

    def execute_task(self, task_id: str) -> dict[str, Any]:
        return self._post(f"/api/v6/tasks/{task_id}/execute")

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self._get(f"/api/v6/tasks/{task_id}")

    def list_tasks(self, status: str = "", limit: int = 20) -> dict[str, Any]:
        params = {"limit": limit}
        if status:
            params["status"] = status
        return self._get("/api/v6/tasks", params)

    # ── Reports ──────────────────────────────────────────────────────────────

    def generate_report(self, task_id: str) -> dict[str, Any]:
        return self._post(f"/api/v6/tasks/{task_id}/report")

    def list_reports(self, limit: int = 10) -> list[dict[str, Any]]:
        data = self._get("/api/v6/reports", {"limit": limit})
        return data if isinstance(data, list) else []

    # ── Evolution ────────────────────────────────────────────────────────────

    def full_analysis(self, files: dict[str, str], req_content: str = "", version: str = "v1.0.0") -> dict[str, Any]:
        return self._post("/api/v7/analyze/full", {
            "files": files,
            "requirements_content": req_content,
            "current_version": version,
        })

    def list_recommendations(self, grouped: bool = True) -> dict[str, Any]:
        return self._get("/api/v7/recommendations/priority" if grouped else "/api/v7/recommendations")

    def approve_recommendation(self, rec_id: str) -> dict[str, Any]:
        return self._post(f"/api/v7/recommendations/{rec_id}/action", {"action": "approve"})

    def dismiss_recommendation(self, rec_id: str) -> dict[str, Any]:
        return self._post(f"/api/v7/recommendations/{rec_id}/action", {"action": "dismiss"})

    def get_recommendation_stats(self) -> dict[str, Any]:
        return self._get("/api/v7/recommendations/stats")

    def get_trends(self) -> dict[str, Any]:
        return self._get("/api/v7/analytics/trends")

    # ── Rollback ─────────────────────────────────────────────────────────────

    def list_checkpoints(self, plan_id: str = "", limit: int = 20) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if plan_id:
            params["plan_id"] = plan_id
        data = self._get("/api/v4/checkpoints", params)
        return data if isinstance(data, list) else []

    def rollback(self, checkpoint_id: str, dry_run: bool = False) -> dict[str, Any]:
        return self._post("/api/v4/rollback", {"checkpoint_id": checkpoint_id, "dry_run": dry_run})

    def list_logs(self, plan_id: str = "", limit: int = 50) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if plan_id:
            params["plan_id"] = plan_id
        data = self._get("/api/v4/execution/logs", params)
        return data if isinstance(data, list) else []

    # ── Daily Brief ──────────────────────────────────────────────────────────

    def daily_brief(self) -> dict[str, Any]:
        return self._get("/api/v7/brief")
