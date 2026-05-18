"""Doctrinal corpus loader and index."""

from __future__ import annotations

from document_intelligence.doctrine.index import DoctrineHit, DoctrineIndex
from document_intelligence.doctrine.loader import DoctrineLoadError, load_doctrine

__all__ = ["DoctrineHit", "DoctrineIndex", "DoctrineLoadError", "load_doctrine"]
