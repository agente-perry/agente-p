"""DoctrineIndex — cosine-similarity index over doctrinal chunks.

The doctrinal corpus is small (~50 entries from the stub, ~few thousand from the
full artifact). A NumPy matrix is enough; FAISS adds no value at this scale and
keeps the doctrine surface trivially serializable.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from document_intelligence.embeddings.base import BaseEmbedder


class DoctrineChunk(BaseModel):
    """Single doctrinal entry (stub or artifact)."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    source: str
    section: str | None = None
    page: int | None = Field(default=None, ge=1)
    text: str
    flag_code: str | None = None


@dataclass(frozen=True)
class DoctrineHit:
    chunk_id: str
    source: str
    section: str | None
    page: int | None
    quote: str
    flag_code: str | None
    score: float


class DoctrineIndex:
    """In-memory cosine index over ``DoctrineChunk`` entries."""

    def __init__(
        self,
        chunks: list[DoctrineChunk],
        vectors: np.ndarray,
        *,
        embedder: BaseEmbedder,
    ) -> None:
        if len(chunks) != vectors.shape[0]:
            raise ValueError("chunks and vectors must have matching length")
        if vectors.shape[1] != embedder.dim:
            raise ValueError(
                f"embedder dim ({embedder.dim}) does not match vectors dim ({vectors.shape[1]})"
            )
        self._chunks = chunks
        self._matrix = vectors.astype(np.float32, copy=False)
        self._embedder = embedder

    @classmethod
    def from_chunks(cls, chunks: list[DoctrineChunk], *, embedder: BaseEmbedder) -> DoctrineIndex:
        if not chunks:
            empty = np.zeros((0, embedder.dim), dtype=np.float32)
            return cls(chunks, empty, embedder=embedder)
        vectors = embedder.embed([c.text for c in chunks])
        return cls(chunks, vectors, embedder=embedder)

    @property
    def size(self) -> int:
        return len(self._chunks)

    @property
    def embedder_model(self) -> str:
        return self._embedder.model_id

    def first_by_flag_code(self, flag_code: str) -> DoctrineHit | None:
        """Deterministic lookup: first chunk whose ``flag_code`` matches.

        Used by ``RiskAnalysisAgent`` when planner could not surface a
        flag-tagged chunk via top-k similarity (frequent with cross-language
        corpus + FakeEmbedder).
        """
        for idx, chunk in enumerate(self._chunks):
            if chunk.flag_code == flag_code:
                vec = self._matrix[idx]
                score = float(vec @ vec)
                return DoctrineHit(
                    chunk_id=chunk.chunk_id,
                    source=chunk.source,
                    section=chunk.section,
                    page=chunk.page,
                    quote=chunk.text,
                    flag_code=chunk.flag_code,
                    score=score,
                )
        return None

    def query_by_ids(self, chunk_ids: list[str]) -> list[DoctrineHit]:
        """Direct lookup by doctrine chunk_id (no vector search)."""
        hits: list[DoctrineHit] = []
        for idx, chunk in enumerate(self._chunks):
            if chunk.chunk_id in chunk_ids:
                vec = self._matrix[idx]
                score = float(vec @ vec)
                hits.append(
                    DoctrineHit(
                        chunk_id=chunk.chunk_id,
                        source=chunk.source,
                        section=chunk.section,
                        page=chunk.page,
                        quote=chunk.text,
                        flag_code=chunk.flag_code,
                        score=score,
                    )
                )
        return hits

    def query(self, text: str, *, top_k: int = 10) -> list[DoctrineHit]:
        if self.size == 0 or top_k <= 0 or not text.strip():
            return []
        query_vec = self._embedder.embed([text])[0]
        scores = self._matrix @ query_vec
        k = min(top_k, scores.shape[0])
        order = np.argpartition(-scores, k - 1)[:k]
        order = order[np.argsort(-scores[order])]
        hits: list[DoctrineHit] = []
        for idx in order:
            chunk = self._chunks[int(idx)]
            hits.append(
                DoctrineHit(
                    chunk_id=chunk.chunk_id,
                    source=chunk.source,
                    section=chunk.section,
                    page=chunk.page,
                    quote=chunk.text,
                    flag_code=chunk.flag_code,
                    score=float(scores[int(idx)]),
                )
            )
        return hits
