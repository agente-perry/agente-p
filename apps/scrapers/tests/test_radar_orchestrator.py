from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from agenteperry.radar import orchestrator
from agenteperry.radar.cli import radar_group
from agenteperry.radar.models import ChangeSet, RadarRunResult, SourceRun


def _records() -> list[dict[str, object]]:
    return [
        {
            "source_code": "ocds_peru",
            "external_id": f"ocds-{index}",
            "record_type": "contract",
            "parsed_data": {"ocid": f"ocds-{index}"},
            "monto": float(index),
        }
        for index in range(3)
    ]


def test_run_source_radar_creates_audit_changed_records_and_hashes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(orchestrator, "_collect_records", lambda **kwargs: _records())

    result = orchestrator.run_source_radar("ocds_peru", limit=2, base_dir=tmp_path)

    assert result.source_run.status == "completed"
    assert result.source_run.records_seen == 2
    assert result.source_run.records_new == 2
    assert result.audit_path.exists()
    assert result.changed_records_path.exists()
    assert result.hashes_path.exists()

    audit = json.loads(result.audit_path.read_text(encoding="utf-8"))
    assert audit["source_run"]["records_seen"] == 2
    assert len(result.changed_records_path.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_run_source_radar_second_run_detects_unchanged(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(orchestrator, "_collect_records", lambda **kwargs: _records())

    first = orchestrator.run_source_radar("ocds_peru", limit=2, base_dir=tmp_path)
    second = orchestrator.run_source_radar("ocds_peru", limit=2, base_dir=tmp_path)

    assert first.source_run.records_new == 2
    assert second.source_run.records_unchanged == 2
    assert second.changed_records_path.read_text(encoding="utf-8") == ""


def test_run_source_radar_analyze_docs_is_placeholder_warning(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(orchestrator, "_collect_records", lambda **kwargs: _records()[:1])

    result = orchestrator.run_source_radar("ocds_peru", analyze_docs=True, base_dir=tmp_path)

    assert any("analyze_docs" in warning for warning in result.source_run.warnings)


def test_run_source_radar_invalid_source_returns_failed_result(tmp_path: Path) -> None:
    result = orchestrator.run_source_radar("missing_source", base_dir=tmp_path)

    assert result.source_run.status == "failed"
    assert result.source_run.errors
    assert result.audit_path.exists()


def test_radar_cli_help() -> None:
    result = CliRunner().invoke(radar_group, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.output
    assert "health" in result.output


def test_radar_cli_health_source(monkeypatch) -> None:
    from agenteperry.radar import health

    monkeypatch.setattr(health, "_light_url_check", lambda url, enabled: True)
    result = CliRunner().invoke(radar_group, ["health", "--source", "ocds_peru"])

    assert result.exit_code == 0
    assert "ocds_peru" in result.output


def test_radar_cli_run_uses_orchestrator(monkeypatch, tmp_path: Path) -> None:
    import agenteperry.radar.cli as radar_cli

    source_run = SourceRun(
        run_id="run-1",
        source_code="ocds_peru",
        mode="incremental",
        status="completed",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
        records_seen=1,
        records_new=1,
    )
    changes = ChangeSet(source_code="ocds_peru", run_id="run-1", records_seen=1, records_new=1)
    fake_result = RadarRunResult(
        source_run=source_run,
        changes=changes,
        audit_path=tmp_path / "audit.json",
        changed_records_path=tmp_path / "changed_records.jsonl",
        hashes_path=tmp_path / "hashes.json",
    )
    monkeypatch.setattr(radar_cli, "run_source_radar", lambda **kwargs: fake_result)

    result = CliRunner().invoke(radar_group, ["run", "--source", "ocds_peru", "--limit", "1"])

    assert result.exit_code == 0
    assert "records_seen" in result.output
