"""Deterministic hash-based embedder for local-first runs and tests.

The vector for a given text is a function of the text alone (and ``dim``),
so the same input always produces the same output. Vectors are L2-normalized.
"""

from __future__ import annotations

import hashlib

import numpy as np


class FakeEmbedder:
    """Deterministic embedder that needs no API key.

    The algorithm hashes whitespace-separated tokens into ``dim`` buckets,
    weights by token frequency, then L2-normalizes. Two identical strings
    always produce the exact same vector.
    """

    model_id: str = "fake-deterministic-v1"

    def __init__(self, dim: int = 256) -> None:
        if dim < 16:
            raise ValueError("dim must be >= 16")
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def _embed_one(self, text: str) -> np.ndarray:
        vec = np.zeros(self._dim, dtype=np.float64)
        if not text:
            return vec.astype(np.float32)
        tokens = text.lower().split()
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self._dim
            sign = 1.0 if (digest[4] & 1) else -1.0
            vec[bucket] += sign
        norm = float(np.linalg.norm(vec))
        if norm > 0.0:
            vec /= norm
        return vec.astype(np.float32)

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32)
        rows = [self._embed_one(t) for t in texts]
        return np.stack(rows, axis=0)
