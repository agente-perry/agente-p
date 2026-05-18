"""Local smoke-search helpers for parsed TDR chunks."""

from __future__ import annotations

import re
import unicodedata

from agenteperry.tdr.models import TdrChunk


def search_chunks(chunks: list[TdrChunk], query: str, *, limit: int = 10) -> list[TdrChunk]:
    normalized_query = _normalize(query)
    if not normalized_query:
        return []
    return [chunk for chunk in chunks if normalized_query in _normalize(chunk.text)][:limit]


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", ascii_text).strip()
