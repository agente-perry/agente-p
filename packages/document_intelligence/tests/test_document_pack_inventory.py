"""Tests for document_pack/inventory.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from document_intelligence.document_pack.inventory import build_inventory
from document_intelligence.document_pack.schemas import ParseStatus


def test_build_inventory_detects_pdfs(tmp_path: Path) -> None:
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except ImportError:  # pragma: no cover
        pytest.skip("reportlab not installed")

    pdf = tmp_path / "test_doc.pdf"
    doc = canvas.Canvas(str(pdf), pagesize=LETTER)
    doc.drawString(72, 740, "OBJETO DEL SERVICIO")
    doc.drawString(72, 720, "Prueba de parsing.")
    doc.showPage()
    doc.save()

    items = build_inventory(tmp_path)
    assert len(items) == 1
    item = items[0]
    assert item.file_name == "test_doc.pdf"
    assert item.sha256 != ""
    assert item.size_bytes > 0
    assert item.pages_total == 1
    assert item.parse_status == ParseStatus.TEXT_OK
    assert item.usable_for_analysis is True


def test_build_inventory_respects_max_docs(tmp_path: Path) -> None:
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except ImportError:  # pragma: no cover
        pytest.skip("reportlab not installed")

    for i in range(5):
        pdf = tmp_path / f"doc_{i}.pdf"
        doc = canvas.Canvas(str(pdf), pagesize=LETTER)
        doc.drawString(72, 740, f"Documento {i}")
        doc.showPage()
        doc.save()

    items = build_inventory(tmp_path, max_docs=3)
    assert len(items) == 3


def test_build_inventory_skips_zone_identifier_files(tmp_path: Path) -> None:
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except ImportError:  # pragma: no cover
        pytest.skip("reportlab not installed")

    pdf = tmp_path / "valid.pdf"
    doc = canvas.Canvas(str(pdf), pagesize=LETTER)
    doc.drawString(72, 740, "texto")
    doc.showPage()
    doc.save()

    (tmp_path / "valid.pdf:Zone.Identifier").write_text("zone data", encoding="utf-8")
    (tmp_path / "other.pdf").write_bytes(b"not a pdf")
    (tmp_path / "backup.pdf.bak").write_bytes(b"backup")

    items = build_inventory(tmp_path)
    names = [i.file_name for i in items]
    assert "valid.pdf" in names
    assert "valid.pdf:Zone.Identifier" not in names
    assert "other.pdf" not in names
    assert "backup.pdf.bak" not in names

    other_item = next((i for i in items if i.file_name == "other.pdf"), None)
    assert other_item is None, "other.pdf is not a valid PDF and should not be in inventory"


def test_build_inventory_usable_flag(tmp_path: Path) -> None:
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except ImportError:  # pragma: no cover
        pytest.skip("reportlab not installed")

    pdf = tmp_path / "text_doc.pdf"
    doc = canvas.Canvas(str(pdf), pagesize=LETTER)
    doc.drawString(72, 740, "Este documento tiene texto suficiente.")
    doc.showPage()
    doc.save()

    items = build_inventory(tmp_path)
    assert items[0].usable_for_analysis is True
    assert items[0].pages_with_text > 0


def test_build_inventory_json_roundtrip(tmp_path: Path) -> None:
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except ImportError:  # pragma: no cover
        pytest.skip("reportlab not installed")

    pdf = tmp_path / "roundtrip.pdf"
    doc = canvas.Canvas(str(pdf), pagesize=LETTER)
    doc.drawString(72, 740, "Contenido.")
    doc.showPage()
    doc.save()

    items = build_inventory(tmp_path)
    serialized = json.dumps([item.to_inventory_dict() for item in items])
    restored = json.loads(serialized)
    assert len(restored) == 1
    assert restored[0]["file_name"] == "roundtrip.pdf"