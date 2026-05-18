"""PDF text extraction with PyMuPDF."""
# pyright: reportMissingTypeStubs=false

from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz

from agenteperry.tdr.models import TdrPage


def extract_pdf_pages(pdf_path: Path, *, tdr_id: str | None = None) -> list[TdrPage]:
    """Extract text page-by-page and preserve auditable page numbers."""
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file, got: {pdf_path}")

    pages: list[TdrPage] = []
    with fitz.open(pdf_path) as document:
        pdf_document: Any = document
        for page_index in range(len(pdf_document)):
            page: Any = pdf_document.load_page(page_index)
            text = str(page.get_text("text") or "")
            pages.append(TdrPage(tdr_id=tdr_id, page_number=page_index + 1, text_content=text.strip()))
    return pages
