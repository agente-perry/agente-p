from __future__ import annotations

from pathlib import Path

import fitz

from agenteperry.ocr.models import PdfOcrClass
from agenteperry.ocr.pdf_classifier import classify_pdf, classify_pdf_dir


def _make_pdf(path: Path, page_texts: list[str]) -> Path:
    doc = fitz.open()
    for text in page_texts:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()
    return path


def test_classify_pdf_textual(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path / "textual.pdf", ["a" * 120, "b" * 120, "c" * 120])
    result = classify_pdf(pdf)
    assert result.classification == PdfOcrClass.TEXTUAL
    assert result.needs_ocr is False
    assert result.pages_total == 3


def test_classify_pdf_scanned(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path / "scanned.pdf", ["", "", ""])
    result = classify_pdf(pdf)
    assert result.classification == PdfOcrClass.SCANNED
    assert result.needs_ocr is True


def test_classify_non_pdf_is_unsupported(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    path.write_text("hello", encoding="utf-8")
    result = classify_pdf(path)
    assert result.classification == PdfOcrClass.UNSUPPORTED
    assert result.needs_ocr is False


def test_sha256_stable(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path / "same.pdf", ["hello world" * 20])
    first = classify_pdf(pdf)
    second = classify_pdf(pdf)
    assert first.sha256 == second.sha256


def test_classify_pdf_dir_recursive(tmp_path: Path) -> None:
    _make_pdf(tmp_path / "a.pdf", ["hello" * 20])
    nested = tmp_path / "nested"
    nested.mkdir()
    _make_pdf(nested / "b.pdf", [""])

    results = classify_pdf_dir(tmp_path, recursive=True)
    assert len(results) == 2
    classes = {item.classification for item in results}
    assert PdfOcrClass.TEXTUAL in classes
    assert PdfOcrClass.SCANNED in classes
