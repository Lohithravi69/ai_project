from __future__ import annotations

import json
import sys
from typing import Any

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from aidev.client import AIClient

console = Console()
client = AIClient()


def _print_json(data: Any) -> None:
    console.print(json.dumps(data, indent=2, default=str))


def _print_error(msg: str) -> None:
    console.print(f"[red]Error:[/red] {msg}")


def _require_backend() -> bool:
    try:
        client._get("/api/v2/repositories")
        return True
    except Exception as e:
        _print_error(f"Cannot reach backend at {client.base_url}: {e}")
        return False


# ── Config ──────────────────────────────────────────────────────────────────


@click.group()
@click.option("--url", "-u", envvar="AIDEV_URL", help="Backend URL", default="")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def main(ctx: click.Context, url: str, json_output: bool) -> None:
    ctx.ensure_object(dict)
    ctx.obj["JSON"] = json_output
    if url:
        global client
        client = AIClient(url)


@main.command()
@click.argument("url", default="http://localhost:8000")
def login(url: str) -> None:
    """Set the backend URL and test connection."""
    try:
        AIClient.save_config(backend_url=url)
        c = AIClient(url)
        c._get("/api/health")
        console.print(f"[green]Connected[/green] to {url}")
    except Exception as e:
        _print_error(f"Cannot connect to {url}: {e}")


@main.command()
def status() -> None:
    """Show backend status and quick summary."""
    if not _require_backend():
        return
    try:
        repos = client.list_repos()
        tasks = client.list_tasks(limit=5)
        stats = client.get_recommendation_stats()
        brief_data = client.daily_brief()

        console.print(Panel("[bold]AI Dev OS[/bold] — Status", expand=False))
        console.print(f"Backend: [green]{client.base_url}[/green]")
        console.print(f"Repositories: [bold]{len(repos)}[/bold]")

        if isinstance(brief_data, dict):
            health = (brief_data.get("health_score", 0) * 100)
            console.print(f"Health: [bold]{health:.0f}%[/bold]")
            metrics = brief_data.get("metrics", [])
            for m in metrics:
                name = m.get("name", "")
                val = m.get("current_value", "")
                unit = m.get("unit", "")
                direction = m.get("direction", "")
                arrow = {"up": "↑", "down": "↓", "stable": "→"}.get(direction, "→")
                color = {"up": "green", "down": "red", "stable": "white"}.get(direction, "white")
                console.print(f"  {name}: [{color}]{val}{unit} {arrow}[/{color}]")

            recs = brief_data.get("recommendations", {})
            console.print(f"Pending recommendations: [bold]{recs.get('open', 0)}[/bold]")
            console.print(f"Experience count: [bold]{brief_data.get('experience_count', 0)}[/bold]")

        if isinstance(tasks, dict):
            task_list = tasks.get("tasks", [])
            if task_list:
                console.print(f"\nRecent tasks: [bold]{len(task_list)}[/bold]")
                for t in task_list[:3]:
                    console.print(f"  [{t.get('status', '?')}] {t.get('objective', '')[:60]}")
    except Exception as e:
        _print_error(str(e))


# ── Repos ───────────────────────────────────────────────────────────────────


@main.command()
def repos() -> None:
    """List registered repositories."""
    if not _require_backend():
        return
    try:
        items = client.list_repos()
        if not items:
            console.print("No repositories registered.")
            return
        table = Table("ID", "Name", "Status", "Language")
        for r in items:
            table.add_row(
                r.get("id", "")[:8],
                r.get("full_name", ""),
                r.get("scan_status", ""),
                str(r.get("language_summary", {}).get("primary_language", "")),
            )
        console.print(table)
    except Exception as e:
        _print_error(str(e))


# ── Plan ────────────────────────────────────────────────────────────────────


@main.command()
@click.argument("objective")
@click.option("--repo", "-r", help="Repository ID")
@click.option("--detail", "-d", help="Additional details")
def plan(objective: str, repo: str, detail: str) -> None:
    """Create an execution plan for an objective."""
    if not _require_backend():
        return
    try:
        request_text = f"{objective}\n{detail}" if detail else objective
        result = client.create_plan(objective, request_text, repo or "")
        plan_id = result.get("id", "")
        console.print(Panel(f"[bold]Plan created[/bold]: {plan_id}", expand=False))
        _print_json(result)
    except Exception as e:
        _print_error(str(e))


# ── Execute ─────────────────────────────────────────────────────────────────


@main.command()
@click.argument("request_text")
@click.option("--repo", "-r", help="Repository ID")
@click.option("--mode", "-m", default="full", type=click.Choice(["full", "plan-only", "code-only"]))
@click.option("--wait", is_flag=True, help="Wait for completion")
def execute(request_text: str, repo: str, mode: str, wait: bool) -> None:
    """Run the agent pipeline for a request."""
    if not _require_backend():
        return
    try:
        result = client.run_agents(request_text, repo or "", mode)
        execution_id = result.get("execution_id", "")
        status = result.get("status", "")
        plan_id = result.get("plan_id", "")

        console.print(f"Execution: [bold]{execution_id[:8]}[/bold]")
        console.print(f"Status: [bold]{status}[/bold]")
        if plan_id:
            console.print(f"Plan: {plan_id}")

        trace = result.get("agent_trace", [])
        if trace:
            table = Table("Agent", "Status", "Duration", "Summary")
            for t in trace:
                table.add_row(
                    t.get("agent_name", ""),
                    "✅" if t.get("success") else "❌",
                    f"{t.get('duration_ms', 0)}ms",
                    t.get("output_summary", "")[:50],
                )
            console.print(table)

        if result.get("result_summary"):
            console.print(f"\nSummary: {result['result_summary']}")

        if json_output:
            _print_json(result)
    except Exception as e:
        _print_error(str(e))


# ── Approve / Review ───────────────────────────────────────────────────────


@main.command()
@click.argument("plan_id")
def review(plan_id: str) -> None:
    """Review a plan's details and trace."""
    if not _require_backend():
        return
    try:
        plan = client.get_plan(plan_id)
        console.print(Panel(f"[bold]Plan:[/bold] {plan.get('objective', '')}", expand=False))
        console.print(f"Risk: {plan.get('risk_score', '?')}")
        console.print(f"Approval: {plan.get('approval_status', '?')}")
        console.print(f"Files: {', '.join(plan.get('affected_files', [])[:10])}")
        trace = plan.get("agent_trace", [])
        if trace:
            console.print("\n[bold]Agent Trace:[/bold]")
            for t in trace:
                console.print(f"  {t.get('agent_name', '')}: {'✅' if t.get('success') else '❌'} {t.get('output_summary', '')[:80]}")
        _print_json(plan)
    except Exception as e:
        _print_error(str(e))


@main.command()
@click.argument("plan_id")
def approve(plan_id: str) -> None:
    """Approve a plan for execution."""
    if not _require_backend():
        return
    try:
        from uuid import uuid4
        result = client._post(f"/api/v4/approval/approve", {"approval_id": plan_id})
        console.print(f"[green]Approved[/green] plan {plan_id[:8]}")
    except Exception as e:
        _print_error(str(e))


# ── Task ────────────────────────────────────────────────────────────────────


@main.command()
@click.argument("objective")
@click.option("--repo", "-r", help="Repository ID")
@click.option("--mode", "-m", default="full")
def task(objective: str, repo: str, mode: str) -> None:
    """Create and run an autonomous task."""
    if not _require_backend():
        return
    try:
        task_data = client.create_task(objective, repo or "", mode)
        task_id = task_data.get("id", "")
        console.print(f"[bold]Task created:[/bold] {task_id[:8]}")

        result = client.execute_task(task_id)
        console.print(f"Status: [bold]{result.get('status', '?')}[/bold]")
        if result.get("result_summary"):
            console.print(f"Summary: {result['result_summary']}")
    except Exception as e:
        _print_error(str(e))


# ── Report ──────────────────────────────────────────────────────────────────


@main.command()
@click.option("--task", "-t", help="Task ID")
@click.option("--latest", "-l", is_flag=True, help="Show latest report")
def report(task: str, latest: bool) -> None:
    """Generate or view execution reports."""
    if not _require_backend():
        return
    try:
        if task:
            result = client.generate_report(task)
            console.print(Panel(f"[bold]{result.get('title', 'Report')}[/bold]", expand=False))
            console.print(result.get("summary", ""))
            for section in result.get("sections", []):
                console.print(f"\n[bold]{section.get('title', '')}[/bold]")
                console.print(section.get("content", "")[:500])
            if result.get("recommendations"):
                console.print("\n[bold]Recommendations:[/bold]")
                for r in result["recommendations"]:
                    console.print(f"  • {r}")
        elif latest:
            reports = client.list_reports(limit=1)
            if reports:
                _print_json(reports[0])
            else:
                console.print("No reports found.")
        else:
            reports = client.list_reports(limit=5)
            if reports:
                console.print(f"[bold]Recent Reports ({len(reports)})[/bold]")
                for r in reports:
                    console.print(f"  • {r.get('title', '')[:80]}")
            else:
                console.print("No reports found.")
    except Exception as e:
        _print_error(str(e))


# ── Evolution ───────────────────────────────────────────────────────────────


@main.command()
@click.option("--files", "-f", multiple=True, help="File:content pairs (file.py:content)")
@click.option("--req", help="Requirements.txt content")
@click.option("--version", "-v", default="v1.0.0")
@click.option("--recommend", is_flag=True, help="Show recommendations after analysis")
def evolve(files: tuple[str], req: str, version: str, recommend: bool) -> None:
    """Run full evolution analysis on code files."""
    if not _require_backend():
        return
    try:
        file_dict: dict[str, str] = {}
        for f in files:
            if ":" in f:
                path, content = f.split(":", 1)
                file_dict[path] = content

        result = client.full_analysis(file_dict, req or "", version)
        console.print(Panel("[bold]Evolution Analysis[/bold]", expand=False))
        console.print(f"Debt items: {result.get('debt_summary', {}).get('total_items', 0)}")
        console.print(f"Arch issues: {result.get('arch_report', {}).get('total_changes', 0)}")
        console.print(f"Security: {result.get('sec_summary', {}).get('total_findings', 0)}")
        console.print(f"Perf issues: {result.get('perf_summary', {}).get('total_findings', 0)}")

        version_plan = result.get("version_plan", {})
        if version_plan:
            console.print(f"\n[bold]Version Plan:[/bold] {version_plan.get('current_version', '')} → {version_plan.get('suggested_version', '')}")
            for reason in version_plan.get("reasons", []):
                console.print(f"  • {reason}")

        if recommend:
            recs = result.get("recommendations", {})
            for priority in ["high", "medium", "low"]:
                items = recs.get(priority, [])
                if items:
                    console.print(f"\n[bold]{priority.upper()} Priority ({len(items)})[/bold]")
                    for item in items[:3]:
                        console.print(f"  • {item.get('title', '')[:80]}")

        if json_output:
            _print_json(result)
    except Exception as e:
        _print_error(str(e))


@main.command()
@click.option("--grouped", is_flag=True, default=True)
def recommendations(grouped: bool) -> None:
    """List prioritized evolution recommendations."""
    if not _require_backend():
        return
    try:
        data = client.list_recommendations(grouped=grouped)
        console.print(Panel("[bold]Recommendations[/bold]", expand=False))

        if grouped and isinstance(data, dict):
            for priority in ["high", "medium", "low"]:
                items = data.get(priority, [])
                if items:
                    color = {"high": "red", "medium": "yellow", "low": "green"}.get(priority, "")
                    console.print(f"\n[{color}]{priority.upper()}: {len(items)}[/{color}]")
                    for item in items[:5]:
                        status = item.get("status", "")
                        marker = "  ✅" if status == "approved" else "  ⏳" if status == "open" else "  ❌"
                        console.print(f"{marker} {item.get('title', '')[:80]}")
        else:
            _print_json(data)
    except Exception as e:
        _print_error(str(e))


@main.command()
@click.argument("rec_id")
@click.argument("action", type=click.Choice(["approve", "dismiss"]))
def recommend(rec_id: str, action: str) -> None:
    """Approve or dismiss a recommendation."""
    if not _require_backend():
        return
    try:
        if action == "approve":
            client.approve_recommendation(rec_id)
        else:
            client.dismiss_recommendation(rec_id)
        console.print(f"[green]{action.capitalize()}d[/green] recommendation {rec_id[:8]}")
    except Exception as e:
        _print_error(str(e))


# ── Analyze ─────────────────────────────────────────────────────────────────


@main.command()
@click.argument("file_path")
def analyze(file_path: str) -> None:
    """Analyze a single file for debt, security, and perf issues."""
    if not _require_backend():
        return
    try:
        import pathlib
        path = pathlib.Path(file_path)
        if not path.exists():
            _print_error(f"File not found: {file_path}")
            return
        content = path.read_text(encoding="utf-8", errors="replace")
        result = client.full_analysis({file_path: content})
        console.print(Panel(f"[bold]Analysis: {file_path}[/bold]", expand=False))
        debt = result.get("debt_summary", {})
        if debt.get("total_items", 0) > 0:
            console.print(f"\n[bold]Technical Debt:[/bold] {debt['total_items']} items (score: {debt.get('debt_ratio', 0)})")
            for cat, info in debt.get("categories", {}).items():
                console.print(f"  • {cat}: {info.get('count', 0)} issues")
        sec = result.get("sec_summary", {})
        if sec.get("total_findings", 0) > 0:
            console.print(f"\n[bold]Security:[/bold] {sec['total_findings']} findings (risk: {sec.get('risk_score', 0)})")
        perf = result.get("perf_summary", {})
        if perf.get("total_findings", 0) > 0:
            console.print(f"\n[bold]Performance:[/bold] {perf['total_findings']} issues")
    except Exception as e:
        _print_error(str(e))


# ── Rollback ────────────────────────────────────────────────────────────────


@main.command()
@click.option("--plan", "-p", help="Plan ID")
@click.option("--checkpoint", "-c", help="Checkpoint ID")
@click.option("--dry-run", is_flag=True, help="Preview without applying")
def rollback(plan: str, checkpoint: str, dry_run: bool) -> None:
    """Roll back to a previous checkpoint."""
    if not _require_backend():
        return
    try:
        if checkpoint:
            result = client.rollback(checkpoint, dry_run)
            console.print(f"Rollback: {'✅' if result.get('success') else '❌'}")
            console.print(f"Summary: {result.get('summary', '')}")
        else:
            items = client.list_checkpoints(plan or "", limit=10)
            if not items:
                console.print("No checkpoints found.")
                return
            table = Table("ID", "Plan", "Tool", "Files", "Created")
            for c in items:
                table.add_row(
                    c.get("id", "")[:8],
                    c.get("plan_id", "")[:8],
                    c.get("tool_name", ""),
                    str(len(c.get("modified_files", []))),
                    str(c.get("created_at", ""))[:10],
                )
            console.print(table)
    except Exception as e:
        _print_error(str(e))


# ── Logs ────────────────────────────────────────────────────────────────────


@main.command()
@click.option("--plan", "-p", help="Plan ID")
@click.option("--limit", "-l", default=30)
def logs(plan: str, limit: int) -> None:
    """View execution logs."""
    if not _require_backend():
        return
    try:
        items = client.list_logs(plan, limit)
        if not items:
            console.print("No logs found.")
            return
        for item in items:
            level = item.get("level", "info")
            color = {"error": "red", "warning": "yellow", "info": "white"}.get(level, "white")
            console.print(f"[{color}]{item.get('created_at', '')[:19]} [{level.upper()}] {item.get('message', '')[:120]}[/{color}]")
    except Exception as e:
        _print_error(str(e))


# ── Brief ───────────────────────────────────────────────────────────────────


@main.command()
def brief() -> None:
    """Show a daily engineering brief."""
    if not _require_backend():
        return
    try:
        data = client.daily_brief()

        console.print(Panel("[bold]Daily Engineering Brief[/bold]", expand=False))

        health_score = data.get("health_score", 0) if isinstance(data, dict) else 0
        improving = data.get("improving", 0)
        declining = data.get("declining", 0)
        stable = data.get("stable", 0)
        console.print(f"\n[bold]Portfolio Health:[/bold] {(health_score * 100):.0f}%")
        console.print(f"  Improving: [green]{improving}[/green] | Declining: [red]{declining}[/red] | Stable: {stable}")

        metrics = data.get("metrics", [])
        for m in metrics:
            name = m.get("name", "")
            val = m.get("current_value", "")
            unit = m.get("unit", "")
            direction = m.get("direction", "")
            arrow = {"up": "↑", "down": "↓", "stable": "→"}.get(direction, "→")
            color = {"up": "green", "down": "red", "stable": "white"}.get(direction, "white")
            console.print(f"  {name}: [{color}]{val}{unit} {arrow}[/{color}]")

        recs = data.get("recommendations", {})
        console.print(f"\n[bold]Recommendations:[/bold] {recs.get('total', 0)} total | {recs.get('open', 0)} pending | {recs.get('approved', 0)} approved")

        repos = data.get("repositories", [])
        if repos:
            console.print(f"\n[bold]Repositories:[/bold] {len(repos)}")
            for r in repos:
                console.print(f"  • {r.get('full_name', '?')} ({r.get('language', '?')})")

        exps = data.get("recent_experiences", [])
        if exps:
            console.print(f"\n[bold]Recent Experiences:[/bold] {len(exps)} (total: {data.get('experience_count', 0)})")
            for e in exps[:3]:
                console.print(f"  • {e.get('outcome', '?')}: {e.get('objective', '')[:60]}")

        console.print(f"\n[dim]aidev status — for detailed status[/dim]")
        console.print(f"[dim]aidev recommendations — to review pending items[/dim]")
    except Exception as e:
        _print_error(str(e))


if __name__ == "__main__":
    main()
