"""CLI commands for the incremental scraping radar."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from agenteperry.radar.health import check_all_sources, check_source_health
from agenteperry.radar.orchestrator import run_source_radar

console = Console()


@click.group("radar")
def radar_group() -> None:
    """Scraping radar: source health, CDC and per-run audits."""


@radar_group.command("run")
@click.option("--source", "source_code", required=True, help="Source code to run (e.g. ocds_peru).")
@click.option("--mode", type=click.Choice(["incremental", "full"]), default="incremental", show_default=True)
@click.option("--limit", type=int, default=None, help="Max records to process.")
@click.option("--analyze-docs", is_flag=True, help="Reserved hook for Activity 8C document analysis.")
@click.option(
    "--base-dir",
    type=click.Path(path_type=Path),
    default=Path("data/runs"),
    show_default=True,
    help="Base directory for radar audit artifacts.",
)
def radar_run(source_code: str, mode: str, limit: int | None, analyze_docs: bool, base_dir: Path) -> None:
    """Run incremental CDC for one source."""
    result = run_source_radar(
        source_code=source_code,
        mode=mode,
        limit=limit,
        analyze_docs=analyze_docs,
        base_dir=base_dir,
    )
    run = result.source_run
    table = Table(title=f"Radar run — {run.source_code}")
    table.add_column("Metric")
    table.add_column("Value")
    for key, value in (
        ("status", run.status),
        ("run_id", run.run_id),
        ("records_seen", run.records_seen),
        ("records_new", run.records_new),
        ("records_changed", run.records_changed),
        ("records_unchanged", run.records_unchanged),
        ("records_failed", run.records_failed),
        ("audit_path", str(result.audit_path)),
        ("changed_records_path", str(result.changed_records_path)),
        ("hashes_path", str(result.hashes_path)),
    ):
        table.add_row(str(key), str(value))
    console.print(table)
    if run.errors:
        raise click.ClickException("; ".join(run.errors))


@radar_group.command("health")
@click.option("--source", "source_code", help="Source code to check.")
@click.option("--all", "all_sources", is_flag=True, help="Check all registered sources.")
def radar_health(source_code: str | None, all_sources: bool) -> None:
    """Check source registry, collector availability and lightweight source health."""
    if not all_sources and not source_code:
        raise click.ClickException("Pass --source <code> or --all")
    checks = check_all_sources() if all_sources else [check_source_health(str(source_code))]

    table = Table(title="Radar source health")
    table.add_column("Source")
    table.add_column("Status")
    table.add_column("Collector")
    table.add_column("Local data")
    table.add_column("URL")
    table.add_column("Error")
    for check in checks:
        table.add_row(
            check.source_code,
            check.status,
            str(check.details.get("collector_available")),
            str(check.local_data_exists),
            str(check.url_reachable),
            check.error or "",
        )
    console.print(table)
    if len(checks) == 1 and checks[0].status == "failed":
        raise click.ClickException(checks[0].error or "health check failed")
