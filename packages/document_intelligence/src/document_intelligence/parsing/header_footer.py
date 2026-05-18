"""Detect and strip repeated headers / footers from a parsed document.

Heuristic: the first non-empty line and the last non-empty line of each page are
candidates. A candidate that appears verbatim on at least ``min_ratio`` of pages
(with at least 3 pages total) is treated as boilerplate and removed.

The detector is conservative on purpose: long lines (likely body text) and
unique lines are never stripped, so we cannot accidentally delete content.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from document_intelligence.schemas.document import DocumentPage

_DEFAULT_MIN_RATIO = 0.5
_DEFAULT_MIN_PAGES = 3
_MAX_CANDIDATE_LEN = 120
_MIN_CANDIDATE_LEN = 2


@dataclass
class HeaderFooterReport:
    """Diagnostic for tests and CLI output."""

    headers: list[str] = field(default_factory=lambda: [])
    footers: list[str] = field(default_factory=lambda: [])
    pages_modified: int = 0


def _first_last_lines(text: str) -> tuple[str | None, str | None]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None, None
    first = lines[0] if _is_candidate(lines[0]) else None
    last = lines[-1] if _is_candidate(lines[-1]) else None
    if first == last:
        last = None
    return first, last


def _is_candidate(line: str) -> bool:
    if len(line) < _MIN_CANDIDATE_LEN or len(line) > _MAX_CANDIDATE_LEN:
        return False
    # Lines that look like prose endings are unlikely to be repeated boilerplate.
    if line.endswith((".", "?", "!")) and len(line.split()) > 6:
        return False
    return True


def detect_repeated_lines(
    pages: list[DocumentPage],
    *,
    min_ratio: float = _DEFAULT_MIN_RATIO,
    min_pages: int = _DEFAULT_MIN_PAGES,
) -> HeaderFooterReport:
    """Return the lines that should be considered boilerplate."""
    if len(pages) < min_pages:
        return HeaderFooterReport()
    head_counts: Counter[str] = Counter()
    foot_counts: Counter[str] = Counter()
    for page in pages:
        first, last = _first_last_lines(page.text)
        if first is not None:
            head_counts[first] += 1
        if last is not None:
            foot_counts[last] += 1
    threshold = max(min_pages, math.ceil(len(pages) * min_ratio))
    headers = [line for line, count in head_counts.items() if count >= threshold]
    footers = [line for line, count in foot_counts.items() if count >= threshold]
    return HeaderFooterReport(headers=headers, footers=footers)


def strip_repeated_lines(
    pages: list[DocumentPage],
    *,
    min_ratio: float = _DEFAULT_MIN_RATIO,
    min_pages: int = _DEFAULT_MIN_PAGES,
) -> tuple[list[DocumentPage], HeaderFooterReport]:
    """Return a copy of ``pages`` with detected headers/footers removed."""
    report = detect_repeated_lines(pages, min_ratio=min_ratio, min_pages=min_pages)
    if not report.headers and not report.footers:
        return list(pages), report

    headers = set(report.headers)
    footers = set(report.footers)
    cleaned: list[DocumentPage] = []
    pages_modified = 0
    for page in pages:
        original = page.text
        if not original:
            cleaned.append(page)
            continue
        lines = original.splitlines()
        changed = False
        # strip leading boilerplate
        while lines and (lines[0].strip() in headers or not lines[0].strip()):
            if lines[0].strip() in headers:
                changed = True
            lines.pop(0)
        # strip trailing boilerplate
        while lines and (lines[-1].strip() in footers or not lines[-1].strip()):
            if lines[-1].strip() in footers:
                changed = True
            lines.pop()
        new_text = "\n".join(lines).strip()
        if changed:
            pages_modified += 1
            cleaned.append(
                page.model_copy(
                    update={
                        "text": new_text,
                        "char_count": len(new_text),
                        "needs_ocr": len(new_text.strip()) < 20,
                    }
                )
            )
        else:
            cleaned.append(page)
    report.pages_modified = pages_modified
    return cleaned, report
