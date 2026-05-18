# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
"""PDF classification for OCR eligibility."""

from __future__ import annotations

import hashlib
from pathlib import Path

import fitz

from agenteperry.ocr.models import PdfClassification, PdfOcrClass


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def classify_pdf(pdf_path: Path, min_chars_per_page: int = 50) -> PdfClassification:
    path = pdf_path.resolve()
    ext = path.suffix.lower()
    if ext != ".pdf":
        return PdfClassification(
            pdf_path=str(path),
            extension=ext,
            pages_total=0,
            pages_with_text=0,
            pages_without_text=0,
            coverage_pct=0.0,
            classification=PdfOcrClass.UNSUPPORTED,
            needs_ocr=False,
            recommended_action="skip_unsupported",
            sha256=_sha256_file(path) if path.exists() else "",
        )

    try:
        with fitz.open(path) as doc:
            total = len(doc)
            with_text = 0
            for page_index in range(total):
                page = doc.load_page(page_index)
                text = str(page.get_text("text") or "").strip()
                if len(text) >= min_chars_per_page:
                    with_text += 1
    except Exception:
        return PdfClassification(
            pdf_path=str(path),
            extension=ext,
            pages_total=0,
            pages_with_text=0,
            pages_without_text=0,
            coverage_pct=0.0,
            classification=PdfOcrClass.UNSUPPORTED,
            needs_ocr=False,
            recommended_action="skip_error",
            sha256=_sha256_file(path) if path.exists() else "",
        )

    without_text = max(total - with_text, 0)
    coverage_pct = round((with_text / total) * 100, 2) if total > 0 else 0.0

    if coverage_pct >= 70:
        klass = PdfOcrClass.TEXTUAL
        needs_ocr = False
        action = "use_digital_text"
    elif coverage_pct >= 20:
        klass = PdfOcrClass.MIXED
        needs_ocr = True
        action = "ocr_missing_pages"
    else:
        klass = PdfOcrClass.SCANNED
        needs_ocr = True
        action = "ocr_all_pages"

    return PdfClassification(
        pdf_path=str(path),
        extension=ext,
        pages_total=total,
        pages_with_text=with_text,
        pages_without_text=without_text,
        coverage_pct=coverage_pct,
        classification=klass,
        needs_ocr=needs_ocr,
        recommended_action=action,
        sha256=_sha256_file(path),
    )


def classify_pdf_dir(input_dir: Path, recursive: bool = True) -> list[PdfClassification]:
    root = input_dir.resolve()
    if root.is_file():
        return [classify_pdf(root)]

    pattern = "**/*" if recursive else "*"
    files = sorted(p for p in root.glob(pattern) if p.is_file())
    results: list[PdfClassification] = []
    for path in files:
        if path.suffix.lower() == ".pdf":
            results.append(classify_pdf(path))
    return results
