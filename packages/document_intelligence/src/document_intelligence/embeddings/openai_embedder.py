"""OpenAI embeddings adapter.

The class fails fast in ``__init__`` when ``OPENAI_API_KEY`` is missing, so the
factory can fall back to a different mode without performing any network call.
"""
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import os
from typing import Any

import numpy as np

_DEFAULT_MODEL = "text-embedding-3-small"
_MODEL_DIMS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


class OpenAIEmbedderError(RuntimeError):
    """Raised when OpenAI credentials or SDK are unavailable."""


class OpenAIEmbedder:
    """OpenAI embeddings client. Calls are made lazily inside ``embed``."""

    def __init__(self, *, model: str = _DEFAULT_MODEL, api_key: str | None = None) -> None:
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise OpenAIEmbedderError(
                "OPENAI_API_KEY is not set. Use mode='mock' for local runs or export the key."
            )
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - extras missing
            raise OpenAIEmbedderError(
                "openai SDK is required for mode='llm'. Install with "
                "`pip install 'document-intelligence[llm]'`."
            ) from exc
        self._client: Any = OpenAI(api_key=key)
        self._model = model
        self._dim = _MODEL_DIMS.get(model, 1536)

    @property
    def model_id(self) -> str:
        return f"openai::{self._model}"

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)
        response = self._client.embeddings.create(model=self._model, input=texts)
        vectors = np.asarray([record.embedding for record in response.data], dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        return vectors / norms
