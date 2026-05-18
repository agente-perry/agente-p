"""Local sentence-transformers adapter. Lazy-imported to keep base install slim."""
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

from typing import Any

import numpy as np


class LocalEmbedderError(RuntimeError):
    """Raised when sentence-transformers cannot be loaded."""


class LocalEmbedder:
    """Wrap a sentence-transformers model behind the embedder protocol."""

    def __init__(self, *, model: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - extras missing
            raise LocalEmbedderError(
                "sentence-transformers not installed. Install with "
                "`pip install 'document-intelligence[local-embed]'`."
            ) from exc
        self._model_name = model
        self._model: Any = SentenceTransformer(model)
        self._dim = int(self._model.get_sentence_embedding_dimension())

    @property
    def model_id(self) -> str:
        return f"local::{self._model_name}"

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)
        vectors = self._model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return np.asarray(vectors, dtype=np.float32)
