"""Embedding adapters and the canonical ``get_embedder`` factory.

Three modes are supported:

- ``mock``: deterministic ``FakeEmbedder``. Default. No API key.
- ``local-embed``: sentence-transformers local model. Requires extras
  ``document-intelligence[local-embed]``.
- ``llm``: OpenAI embeddings. Requires ``OPENAI_API_KEY``.
"""

from __future__ import annotations

from typing import Literal

from document_intelligence.embeddings.base import BaseEmbedder
from document_intelligence.embeddings.fake_embedder import FakeEmbedder
from document_intelligence.embeddings.openai_embedder import (
    OpenAIEmbedder,
    OpenAIEmbedderError,
)

EmbedderMode = Literal["mock", "local-embed", "llm"]

__all__ = [
    "BaseEmbedder",
    "EmbedderMode",
    "FakeEmbedder",
    "OpenAIEmbedder",
    "OpenAIEmbedderError",
    "get_default_embedder",
    "get_embedder",
]


def get_embedder(
    mode: EmbedderMode = "mock",
    *,
    model: str | None = None,
    dim: int = 256,
) -> BaseEmbedder:
    """Return an embedder for the requested mode.

    Failures from optional providers are raised so callers can decide whether
    to fall back; the function itself does not silently downgrade.
    """
    if mode == "mock":
        return FakeEmbedder(dim=dim)
    if mode == "llm":
        return OpenAIEmbedder(model=model or "text-embedding-3-small")
    if mode == "local-embed":
        try:
            from document_intelligence.embeddings.local_embedder import LocalEmbedder
        except ImportError as exc:
            raise RuntimeError(
                "Install 'document-intelligence[local-embed]' to use mode='local-embed'."
            ) from exc
        return LocalEmbedder(model=model or "sentence-transformers/all-MiniLM-L6-v2")
    raise ValueError(f"Unknown embedder mode: {mode!r}")


def get_default_embedder(dim: int = 256) -> BaseEmbedder:
    """Back-compat alias for ``get_embedder('mock')``."""
    return get_embedder("mock", dim=dim)
