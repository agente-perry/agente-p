"""Chunk TDR text for search and embeddings."""

from __future__ import annotations

import re

from agenteperry.tdr.models import TdrChunk, TdrPage


def chunk_pages(pages: list[TdrPage], *, max_chars: int = 1200, overlap_chars: int = 160) -> list[TdrChunk]:
    """Split pages into overlapping chunks while preserving page provenance."""
    if max_chars < 200:
        raise ValueError("max_chars must be at least 200")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be non-negative and smaller than max_chars")

    chunks: list[TdrChunk] = []
    for page in pages:
        text = _normalize_whitespace(page.text_content)
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            if end < len(text):
                end = _rewind_to_word_boundary(text, start, end)
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(
                    TdrChunk(
                        tdr_id=page.tdr_id,
                        chunk_index=len(chunks),
                        page_start=page.page_number,
                        page_end=page.page_number,
                        text=chunk_text,
                        metadata={"char_start": start, "char_end": end},
                    )
                )
            if end >= len(text):
                break
            start = max(end - overlap_chars, 0)
    return chunks


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _rewind_to_word_boundary(text: str, start: int, end: int) -> int:
    boundary = text.rfind(" ", start + 1, end)
    return end if boundary <= start else boundary
