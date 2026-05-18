"""Embedder interface."""

from __future__ import annotations

from typing import Protocol

import numpy as np


class BaseEmbedder(Protocol):
    """Minimal embedder contract.

    Implementations must be deterministic for any given (text, model_version) pair
    in modes that promise reproducibility (used by tests).
    """

    @property
    def dim(self) -> int:
        ...

    @property
    def model_id(self) -> str:
        ...

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return a ``(len(texts), dim)`` float32 matrix. Rows are L2-normalized."""
        ...
