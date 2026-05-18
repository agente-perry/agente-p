"""Debug retrieval integration tests (PR #8)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def test_debug_retrieval_flag_produces_diagnostic_blob(tmp_path: Path) -> None:
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except ImportError:
        pytest.skip("reportlab not installed")

    pdf_path = tmp_path / "debug_test.pdf"
    doc = canvas.Canvas(str(pdf_path), pagesize=LETTER)
    doc.drawString(72, 740, "OBJETO DEL SERVICIO")
    doc.drawString(72, 722, "Experiencia minima de diez anos en el mismo sector.")
    doc.drawString(72, 704, "La propuesta sera evaluada a juicio del comite tecnico.")
    doc.showPage()
    doc.save()

    out_path = tmp_path / "analysis.json"

    venv_python = (
        Path(sys.executable)
        if not _repo_root().joinpath("packages/document_intelligence/.venv/bin/python").exists()
        else _repo_root() / "packages/document_intelligence/.venv/bin/python"
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(_repo_root() / "packages/document_intelligence" / "src")

    completed = subprocess.run(
        [
            str(venv_python),
            "-m",
            "document_intelligence.cli",
            "analyze",
            str(pdf_path),
            "--question",
            "Detecta señales de baja trazabilidad y requisitos restrictivos",
            "--ocr",
            "off",
            "--debug-retrieval",
            "--output",
            str(out_path),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr

    result = json.loads(out_path.read_text(encoding="utf-8"))
    assert "debug_retrieval" in result
    dr = result["debug_retrieval"]

    required_keys = {
        "question",
        "planner",
        "clusters_selected",
        "queries_generated",
        "retrieval_hits",
        "candidate_patterns_seen",
        "flags_candidate_count",
        "flags_accepted_count",
        "flags_rejected_count",
    }
    assert required_keys.issubset(dr.keys()), f"missing keys: {required_keys - dr.keys()}"

    planner = dr["planner"]
    assert "expansion_sources" in planner
    assert "intent_matches" in planner

    assert len(dr["queries_generated"]) > 0
    for q in dr["queries_generated"]:
        assert "flag_code" in q
        assert "query_text" in q
        assert "target_clusters" in q


def test_general_question_triggers_risk_scan_expansion(tmp_path: Path) -> None:
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except ImportError:
        pytest.skip("reportlab not installed")

    pdf_path = tmp_path / "expansion_test.pdf"
    doc = canvas.Canvas(str(pdf_path), pagesize=LETTER)
    doc.drawString(72, 740, "OBJETO: Servicio de consultoria ambiental.")
    doc.showPage()
    doc.save()

    out_path = tmp_path / "analysis.json"

    venv_python = (
        Path(sys.executable)
        if not _repo_root().joinpath("packages/document_intelligence/.venv/bin/python").exists()
        else _repo_root() / "packages/document_intelligence/.venv/bin/python"
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(_repo_root() / "packages/document_intelligence" / "src")

    completed = subprocess.run(
        [
            str(venv_python),
            "-m",
            "document_intelligence.cli",
            "analyze",
            str(pdf_path),
            "--question",
            "Detecta señales de baja trazabilidad y requisitos restrictivos",
            "--ocr",
            "off",
            "--debug-retrieval",
            "--output",
            str(out_path),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr

    result = json.loads(out_path.read_text(encoding="utf-8"))
    dr = result["debug_retrieval"]

    assert "intent::risk_scan" in dr["planner"]["expansion_sources"]
    assert "risk_scan" in dr["planner"]["intent_matches"]

    flag_codes = {q["flag_code"] for q in dr["queries_generated"]}
    assert len(flag_codes) >= 4


def test_retriever_preserves_target_flag_code(tmp_path: Path) -> None:
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except ImportError:
        pytest.skip("reportlab not installed")

    pdf_path = tmp_path / "retriever_test.pdf"
    doc = canvas.Canvas(str(pdf_path), pagesize=LETTER)
    doc.drawString(72, 740, "OBJETO: Servicio de limpeza.")
    doc.drawString(72, 722, "Experiencia minima de cinco anos.")
    doc.showPage()
    doc.save()

    out_path = tmp_path / "analysis.json"

    venv_python = (
        Path(sys.executable)
        if not _repo_root().joinpath("packages/document_intelligence/.venv/bin/python").exists()
        else _repo_root() / "packages/document_intelligence/.venv/bin/python"
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(_repo_root() / "packages/document_intelligence" / "src")

    completed = subprocess.run(
        [
            str(venv_python),
            "-m",
            "document_intelligence.cli",
            "analyze",
            str(pdf_path),
            "--question",
            "Detecta señales de baja trazabilidad y requisitos restrictivos",
            "--ocr",
            "off",
            "--debug-retrieval",
            "--output",
            str(out_path),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr

    result = json.loads(out_path.read_text(encoding="utf-8"))
    dr = result["debug_retrieval"]

    for hit in dr["retrieval_hits"]:
        assert "flag_code" in hit
        assert "query" in hit
        assert "chunk_id" in hit


def test_no_false_positives_from_boilerplate(tmp_path: Path) -> None:
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except ImportError:
        pytest.skip("reportlab not installed")

    pdf_path = tmp_path / "boilerplate_test.pdf"
    doc = canvas.Canvas(str(pdf_path), pagesize=LETTER)
    doc.drawString(72, 740, "DECLARACION JURADA DE CUMPLIMIENTO")
    doc.drawString(72, 722, "El postor declara bajo juramento que cumple con los requisitos.")
    doc.drawString(72, 704, "Anexo N: Formato de presentacion.")
    doc.drawString(72, 686, "Presentacion en formato digital via SEACE.")
    doc.showPage()
    doc.save()

    out_path = tmp_path / "analysis.json"

    venv_python = (
        Path(sys.executable)
        if not _repo_root().joinpath("packages/document_intelligence/.venv/bin/python").exists()
        else _repo_root() / "packages/document_intelligence/.venv/bin/python"
    )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(_repo_root() / "packages/document_intelligence" / "src")

    completed = subprocess.run(
        [
            str(venv_python),
            "-m",
            "document_intelligence.cli",
            "analyze",
            str(pdf_path),
            "--question",
            "Detecta señales de baja trazabilidad y requisitos restrictivos",
            "--ocr",
            "off",
            "--debug-retrieval",
            "--output",
            str(out_path),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr

    result = json.loads(out_path.read_text(encoding="utf-8"))
    assert "flags" in result
    assert "debug_retrieval" in result

    dr = result["debug_retrieval"]
    assert dr["flags_candidate_count"] == 0
    assert dr["flags_accepted_count"] == 0


def test_debug_payload_includes_flags_rejected_reasons(tmp_path: Path) -> None:
    """The diagnostic blob must surface reject_reasons so the team can debug
    why candidates that hit a pattern still get dropped (anti-hallucination,
    missing doctrine anchor, low confidence)."""
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except ImportError:
        pytest.skip("reportlab not installed")

    pdf_path = tmp_path / "reasons_test.pdf"
    doc = canvas.Canvas(str(pdf_path), pagesize=LETTER)
    doc.drawString(72, 740, "OBJETO: Servicio de monitoreo.")
    doc.showPage()
    doc.save()

    out_path = tmp_path / "analysis.json"
    venv_python = (
        Path(sys.executable)
        if not _repo_root().joinpath("packages/document_intelligence/.venv/bin/python").exists()
        else _repo_root() / "packages/document_intelligence/.venv/bin/python"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_repo_root() / "packages/document_intelligence" / "src")

    completed = subprocess.run(
        [
            str(venv_python),
            "-m",
            "document_intelligence.cli",
            "analyze",
            str(pdf_path),
            "--question",
            "Detecta señales de baja trazabilidad y requisitos restrictivos",
            "--ocr",
            "off",
            "--debug-retrieval",
            "--output",
            str(out_path),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr

    dr = json.loads(out_path.read_text(encoding="utf-8"))["debug_retrieval"]
    assert "flags_rejected_reasons" in dr
    assert isinstance(dr["flags_rejected_reasons"], list)
    # Per parallel-list contract: one reason string per rejected candidate.
    assert len(dr["flags_rejected_reasons"]) == dr["flags_rejected_count"]


def test_critique_reject_reasons_unit() -> None:
    """Unit-level: CriticCritique.reject_reasons populated when dual evidence missing."""
    from document_intelligence.agents.evidence_critic import (
        CriticConfig,
        EvidenceCriticAgent,
    )
    from document_intelligence.schemas.analysis import FlagCandidate
    from document_intelligence.schemas.evidence import EvidenceItem

    cand = FlagCandidate(
        flag_code="OBSOLETE_PHYSICAL_FORMAT",
        flag_name="Entregable fisico",
        severity="medium",
        tdr_evidence=EvidenceItem(chunk_id="d::00001", page_number=3, quote="impreso A3"),
        doctrine_anchor=None,
        explanation="test",
        confidence=0.6,
    )
    critique = EvidenceCriticAgent(
        config=CriticConfig(require_dual_evidence=True)
    ).critique([cand])
    assert critique.accepted == []
    assert critique.rejected == [cand]
    assert critique.reject_reasons
    assert "OBSOLETE_PHYSICAL_FORMAT" in critique.reject_reasons[0]


def test_critique_reject_reasons_empty_for_clean_critique() -> None:
    """No candidates → no reject_reasons entries."""
    from document_intelligence.agents.evidence_critic import EvidenceCriticAgent

    critique = EvidenceCriticAgent().critique([])
    assert critique.reject_reasons == []
    assert critique.needs_replan is False