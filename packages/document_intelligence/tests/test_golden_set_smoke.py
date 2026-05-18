"""Smoke test for ``scripts/run_golden_set.py`` against a synthetic fixture."""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _repo_root() -> Path:
    # tests/ -> document_intelligence/ -> packages/ -> repo root.
    return Path(__file__).resolve().parents[3]


def _make_synthetic_pdf(path: Path) -> None:
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except ImportError:  # pragma: no cover
        pytest.skip("reportlab not installed")

    pages = [
        "OBJETO DEL SERVICIO\nServicio integral de consultoria.",
        "EXPERIENCIA DEL POSTOR\nExperiencia minima de diez anos en el mismo sector.",
        (
            "ENTREGABLES\nEl informe final debera presentarse impreso en formato A3 "
            "y en dos ejemplares originales. No se requiere base de datos estructurada."
        ),
        "CRITERIOS DE EVALUACION\nLa propuesta sera evaluada conforme al juicio del comite tecnico.",
    ]
    doc = canvas.Canvas(str(path), pagesize=LETTER)
    for body in pages:
        y = 740
        for line in body.splitlines():
            doc.drawString(72, y, line)
            y -= 18
        doc.showPage()
    doc.save()


def test_run_golden_set_writes_summary(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    out_dir = tmp_path / "outputs"

    pdf_path = pdf_dir / "smoke_001.pdf"
    _make_synthetic_pdf(pdf_path)

    metadata_path = tmp_path / "metadata.csv"
    with metadata_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "id",
                "file_name",
                "sector",
                "entity_name",
                "procedure_code",
                "source_url",
                "file_url",
                "document_type",
                "pages",
                "reason_selected",
                "expected_flags",
                "question",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "id": "smoke_001",
                "file_name": "smoke_001.pdf",
                "sector": "test",
                "entity_name": "Test Entity",
                "procedure_code": "TEST-001",
                "source_url": "",
                "file_url": "",
                "document_type": "bases",
                "pages": "4",
                "reason_selected": "smoke test fixture",
                "expected_flags": "OBSOLETE_PHYSICAL_FORMAT;SUBJECTIVE_EVALUATION_CRITERIA",
                "question": "Detecta senales de baja trazabilidad y requisitos restrictivos.",
            }
        )

    script_path = _repo_root() / "scripts" / "run_golden_set.py"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_repo_root() / "packages" / "document_intelligence" / "src")

    completed = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--metadata",
            str(metadata_path),
            "--pdf-dir",
            str(pdf_dir),
            "--out",
            str(out_dir),
            "--python",
            sys.executable,
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    # Exit code may be 1 only if there were errors. With a real fixture there
    # should be none.
    assert completed.returncode == 0, completed.stderr or completed.stdout

    summary_path = out_dir / "summary.json"
    assert summary_path.exists(), "summary.json was not produced"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert summary["documents_total"] == 1
    assert summary["documents_analyzed"] == 1
    assert summary["errors"] == []
    assert "smoke_001" in summary["per_document"]
    per_doc = summary["per_document"]["smoke_001"]
    assert per_doc["expected"]
    assert "precision_estimate" in per_doc
    assert "recall_estimate" in per_doc

    analysis_path = out_dir / "smoke_001.analysis.json"
    assert analysis_path.exists()
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    assert "flags" in analysis
    assert "disclaimer" in analysis


def test_run_golden_set_reports_missing_pdf(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    out_dir = tmp_path / "outputs"

    metadata_path = tmp_path / "metadata.csv"
    with metadata_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["id", "file_name", "document_type", "expected_flags"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "id": "missing_001",
                "file_name": "does_not_exist.pdf",
                "document_type": "bases",
                "expected_flags": "",
            }
        )

    script_path = _repo_root() / "scripts" / "run_golden_set.py"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_repo_root() / "packages" / "document_intelligence" / "src")

    completed = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--metadata",
            str(metadata_path),
            "--pdf-dir",
            str(pdf_dir),
            "--out",
            str(out_dir),
            "--python",
            sys.executable,
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    # missing PDF is reported as an error → exit 1.
    assert completed.returncode == 1
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["documents_analyzed"] == 0
    assert summary["errors"]
    assert summary["errors"][0]["status"] == "missing_pdf"
