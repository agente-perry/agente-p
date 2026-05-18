"""Whitespace and noise cleanup for page text."""

from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"[ \t]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_TRAILING_SPACE_RE = re.compile(r"[ \t]+\n")
_HYPHENATED_LINEBREAK_RE = re.compile(r"(\w)-\n(\w)")


def clean_page_text(text: str) -> str:
    """Conservative cleanup that preserves page-internal structure.

    - collapses runs of spaces/tabs
    - removes trailing whitespace before newlines
    - collapses 3+ newlines to 2
    - rejoins words split across line breaks by hyphenation
    """
    if not text:
        return ""
    cleaned = _HYPHENATED_LINEBREAK_RE.sub(r"\1\2", text)
    cleaned = _TRAILING_SPACE_RE.sub("\n", cleaned)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned)
    cleaned = _MULTI_NEWLINE_RE.sub("\n\n", cleaned)
    return cleaned.strip()
