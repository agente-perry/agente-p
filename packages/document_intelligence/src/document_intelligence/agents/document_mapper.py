"""DocumentMapperAgent — detect canonical sections in a TDR via heading heuristics.

The agent walks the parsed pages, scans each line, and decides whether the line
is a heading that belongs to one of the canonical clusters defined in
``flags/cluster_catalog.yaml``. Detected sections are stitched together so each
section spans from its heading page to the page where the next heading appears.

This is the mock-mode implementation. The optional LLM-refined mode arrives in
PR #4 with the orchestrator; the contract returned here stays stable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from document_intelligence.agents._canonical import (
    OTHERS_LABEL,
    load_cluster_catalog,
    normalize,
)
from document_intelligence.schemas.document import DocumentPage
from document_intelligence.schemas.plan import DocumentSection, TDRMap

_HEADING_LINE_RE = re.compile(
    r"^\s*(?:[IVXLCDM]+\.\s+|[0-9]+(?:\.[0-9]+)*\.?\s+)?[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9 /,\-:]{3,}\s*$"
)
_MAX_HEADING_LEN = 120


@dataclass(frozen=True)
class _HeadingHit:
    page_number: int
    label: str
    heading_raw: str


def _iter_heading_hits(pages: list[DocumentPage]) -> list[_HeadingHit]:
    catalog = load_cluster_catalog()
    hits: list[_HeadingHit] = []
    for page in pages:
        if not page.text:
            continue
        for raw_line in page.text.splitlines():
            line = raw_line.strip()
            if not line or len(line) > _MAX_HEADING_LEN:
                continue
            if not _HEADING_LINE_RE.match(line):
                continue
            normalized = normalize(line)
            matched: str | None = None
            for definition in catalog:
                for keyword in definition.keywords:
                    if keyword in normalized:
                        matched = definition.label
                        break
                if matched is not None:
                    break
            if matched is not None:
                hits.append(_HeadingHit(page.page_number, matched, line))
    return hits


def _merge_hits(hits: list[_HeadingHit], total_pages: int) -> list[DocumentSection]:
    if not hits:
        return []
    sections: list[DocumentSection] = []
    for index, hit in enumerate(hits):
        page_end = (
            hits[index + 1].page_number - 1 if index + 1 < len(hits) else total_pages
        )
        page_end = max(page_end, hit.page_number)
        # Collapse adjacent duplicates of the same label.
        if sections and sections[-1].name == hit.label and sections[-1].page_end + 1 >= hit.page_number:
            previous = sections[-1]
            sections[-1] = DocumentSection(
                name=previous.name,
                page_start=previous.page_start,
                page_end=max(previous.page_end, page_end),
                heading_raw=previous.heading_raw,
            )
            continue
        sections.append(
            DocumentSection(
                name=hit.label,
                page_start=hit.page_number,
                page_end=page_end,
                heading_raw=hit.heading_raw,
            )
        )
    return sections


def map_document(document_id: str, pages: list[DocumentPage]) -> TDRMap:
    """Build a ``TDRMap`` from parsed pages."""
    if not pages:
        return TDRMap(document_id=document_id, sections=[], unmatched_pages=[])
    total_pages = max(p.page_number for p in pages)
    hits = _iter_heading_hits(pages)
    sections = _merge_hits(hits, total_pages)
    covered: set[int] = set()
    for section in sections:
        covered.update(range(section.page_start, section.page_end + 1))
    unmatched = [p.page_number for p in pages if p.page_number not in covered]
    return TDRMap(document_id=document_id, sections=sections, unmatched_pages=unmatched)


class DocumentMapperAgent:
    """Thin OO wrapper around ``map_document`` so the agent layer is uniform."""

    def __call__(self, document_id: str, pages: list[DocumentPage]) -> TDRMap:
        return map_document(document_id, pages)

    @staticmethod
    def canonical_others() -> str:
        return OTHERS_LABEL
