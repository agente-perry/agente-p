"""Golden set batch runner passes --ocr to analyze and reports OCR section."""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _make_text_pdf(path: Path) -> None:
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except ImportError:  # pragma: no cover
        pytest.skip("reportlab not installed")
    doc = canvas.Canvas(str(path), pagesize=LETTER)
    bodies = [
        "OBJETO DEL SERVICIO\nServicio integral con texto suficiente para parseo.",
        "ENTREGABLES\nEl informe final debera presentarse impreso en formato A3.",
    ]
    for body in bodies:
        y = 740
        for line in body.splitlines():
            doc.drawString(72, y, line)
            y -= 18
        doc.showPage()
    doc.save()


def _make_scanned_pdf(path: Path) -> None:
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except ImportError:  # pragma: no cover
        pytest.skip("reportlab not installed")
    doc = canvas.Canvas(str(path), pagesize=LETTER)
    for _ in range(2):
        doc.rect(72, 72, 200, 200, stroke=1, fill=0)
        doc.showPage()
    doc.save()


def _write_metadata(metadata_path: Path, pdf_filename: str) -> None:
    with metadata_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "id",
                "file_name",
                "document_type",
                "expected_flags",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "id": "ocr_001",
                "file_name": pdf_filename,
                "document_type": "bases",
                "expected_flags": "",
            }
        )


def test_run_golden_set_passes_ocr_flag(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    out_dir = tmp_path / "outputs"

    pdf_path = pdf_dir / "ocr_001.pdf"
    _make_text_pdf(pdf_path)

    metadata_path = tmp_path / "metadata.csv"
    _write_metadata(metadata_path, "ocr_001.pdf")

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
            "--ocr",
            "off",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout

    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert "ocr" in summary
    assert summary["ocr"]["mode"] == "off"
    assert summary["ocr"]["pages_ocr_applied"] == 0
    assert "--ocr" in summary["command_default"]


def test_run_golden_set_reports_documents_needing_ocr(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    out_dir = tmp_path / "outputs"

    pdf_path = pdf_dir / "ocr_scan_001.pdf"
    _make_scanned_pdf(pdf_path)

    metadata_path = tmp_path / "metadata.csv"
    _write_metadata(metadata_path, "ocr_scan_001.pdf")

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
            "--ocr",
            "auto",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout

    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["ocr"]["mode"] == "auto"
    assert summary["ocr"]["documents_needing_ocr"] == 1
    assert summary["ocr"]["pages_needing_ocr"] == 2
    assert "ocr_available" in summary["ocr"]
