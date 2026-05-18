"""PR #14 — Batch runner integration tests (apps/scrapers venv).

This venv has both ``langgraph`` and ``agenteperry.tdr.auditor`` available,
so the AuditorGraph delegation through ``document_intelligence`` runs end
to end.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "validate_seace_batch.py"
FIXTURE = (
    REPO_ROOT
    / "data"
    / "scraped"
    / "seace_salud"
    / "manifests"
    / "process_document_packs.example.jsonl"
)


def _load_runner_module():
    if "validate_seace_batch" in sys.modules:
        return sys.modules["validate_seace_batch"]
    spec = importlib.util.spec_from_file_location("validate_seace_batch", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_seace_batch"] = module
    spec.loader.exec_module(module)
    return module


def test_runner_loads_fixture_and_emits_metrics(tmp_path: Path) -> None:
    if not FIXTURE.exists():
        pytest.skip("fixture not present")
    mod = _load_runner_module()
    metrics = mod.run(FIXTURE, outputs_root=tmp_path / "outputs", reports_root=tmp_path / "reports")
    required = {
        "packs_total", "packs_valid", "packs_rejected",
        "packs_runnable_by_auditor", "preventive_count", "investigative_count",
        "packs_with_supplier_ruc", "packs_with_award_quote",
        "packs_score_50_plus", "packs_score_75_plus", "graph_rag_candidates",
        "flags_by_code", "risk_distribution", "score_distribution",
    }
    missing = required - set(metrics.keys())
    assert not missing
    assert metrics["packs_total"] == metrics["packs_valid"] + metrics["packs_rejected"]
    assert metrics["packs_valid"] >= 1
    assert metrics["packs_runnable_by_auditor"] >= 1


def test_runner_writes_markdown_and_json_artifacts(tmp_path: Path) -> None:
    if not FIXTURE.exists():
        pytest.skip("fixture not present")
    mod = _load_runner_module()
    outputs = tmp_path / "outputs"
    reports = tmp_path / "reports"
    metrics = mod.run(FIXTURE, outputs_root=outputs, reports_root=reports)
    report_md = reports / f"{FIXTURE.stem}_validation.md"
    summary_json = reports / f"{FIXTURE.stem}_summary.json"
    assert report_md.exists()
    assert summary_json.exists()
    assert "Batch Validation Report" in report_md.read_text(encoding="utf-8")
    parsed = json.loads(summary_json.read_text(encoding="utf-8"))
    assert parsed["packs_valid"] == metrics["packs_valid"]


def test_runner_never_activates_graphrag(tmp_path: Path) -> None:
    if not FIXTURE.exists():
        pytest.skip("fixture not present")
    mod = _load_runner_module()
    outputs = tmp_path / "outputs"
    mod.run(FIXTURE, outputs_root=outputs, reports_root=tmp_path / "reports")
    files = list((outputs / FIXTURE.stem).glob("*.auditor.json"))
    assert files
    for f in files:
        payload = json.loads(f.read_text(encoding="utf-8"))
        assert payload.get("graph_rag_activation") is False


def test_runner_reports_graphrag_blockers(tmp_path: Path) -> None:
    if not FIXTURE.exists():
        pytest.skip("fixture not present")
    mod = _load_runner_module()
    outputs = tmp_path / "outputs"
    mod.run(FIXTURE, outputs_root=outputs, reports_root=tmp_path / "reports")
    payloads = [
        json.loads(f.read_text(encoding="utf-8"))
        for f in (outputs / FIXTURE.stem).glob("*.auditor.json")
    ]
    assert any(
        any(b.startswith("score_below_threshold") for b in p.get("graph_rag_blockers", []))
        for p in payloads
    )


def test_runner_handles_missing_manifest(tmp_path: Path) -> None:
    mod = _load_runner_module()
    nonexistent = tmp_path / "does_not_exist.jsonl"
    with pytest.raises(SystemExit):
        mod.run(nonexistent, outputs_root=tmp_path / "outputs", reports_root=tmp_path / "reports")


def test_runner_handles_empty_manifest(tmp_path: Path) -> None:
    mod = _load_runner_module()
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    metrics = mod.run(empty, outputs_root=tmp_path / "outputs", reports_root=tmp_path / "reports")
    assert metrics["packs_total"] == 0
    assert metrics["packs_valid"] == 0
    assert metrics["graph_rag_candidates"] == 0
