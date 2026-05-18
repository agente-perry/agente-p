"""TDRIndex — hybrid FAISS HNSW + BM25 retrieval with disk persistence.

Vector retrieval uses FAISS ``IndexHNSWFlat`` with inner-product metric over
L2-normalized vectors (cosine equivalence). Lexical retrieval uses ``rank_bm25``
rebuilt at load time from the persisted chunk text. Final ranking fuses both
rankers with Reciprocal Rank Fusion (k=60).

On-disk layout (``~/.cache/document_intelligence/tdr_index/<document_id>/``)::

    manifest.json   embedder model id, dim, chunk count, bm25 params, version
    chunks.jsonl    persisted DocumentChunk rows
    vectors.faiss   FAISS HNSW binary
"""
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportCallIssue=false

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import faiss
import numpy as np
from rank_bm25 import BM25Okapi

from document_intelligence.embeddings.base import BaseEmbedder
from document_intelligence.schemas.chunk import DocumentChunk

_DEFAULT_CACHE = Path.home() / ".cache" / "document_intelligence" / "tdr_index"
_INDEX_VERSION = 1
_HNSW_M = 32
_HNSW_EF_CONSTRUCTION = 200
_HNSW_EF_SEARCH = 64
_RRF_K = 60


@dataclass(frozen=True)
class RetrievalHit:
    """One ranked retrieval result. ``score`` is the fused RRF score."""

    chunk_id: str
    page_start: int
    page_end: int
    text_excerpt: str
    score: float
    vector_score: float
    bm25_score: float
    cluster_hint: str | None


def _tokenize(text: str) -> list[str]:
    return [token for token in text.lower().split() if token]


def _cluster_value(chunk: DocumentChunk) -> str | None:
    cluster_meta = chunk.metadata.get("cluster_label") if chunk.metadata else None
    if isinstance(cluster_meta, str) and cluster_meta:
        return cluster_meta
    return chunk.section_hint


class TDRIndex:
    """Hybrid retrieval index for a single document."""

    def __init__(
        self,
        document_id: str,
        chunks: list[DocumentChunk],
        vectors: np.ndarray,
        embedder: BaseEmbedder,
    ) -> None:
        if vectors.shape != (len(chunks), embedder.dim):
            raise ValueError(
                f"vectors shape {vectors.shape} does not match "
                f"({len(chunks)}, {embedder.dim})"
            )
        self._document_id = document_id
        self._chunks = chunks
        self._embedder = embedder
        self._faiss = self._build_faiss(vectors.astype(np.float32, copy=False), embedder.dim)
        self._bm25 = (
            BM25Okapi([_tokenize(c.text) for c in chunks]) if chunks else None
        )

    @staticmethod
    def _build_faiss(vectors: np.ndarray, dim: int) -> Any:
        index = faiss.IndexHNSWFlat(dim, _HNSW_M, faiss.METRIC_INNER_PRODUCT)
        index.hnsw.efConstruction = _HNSW_EF_CONSTRUCTION
        index.hnsw.efSearch = _HNSW_EF_SEARCH
        if vectors.shape[0]:
            index.add(vectors)
        return index

    @classmethod
    def build(
        cls,
        *,
        document_id: str,
        chunks: list[DocumentChunk],
        embedder: BaseEmbedder,
    ) -> TDRIndex:
        if not chunks:
            empty = np.zeros((0, embedder.dim), dtype=np.float32)
            return cls(document_id, chunks, empty, embedder)
        vectors = embedder.embed([c.text for c in chunks])
        return cls(document_id, chunks, vectors, embedder)

    @property
    def document_id(self) -> str:
        return self._document_id

    @property
    def size(self) -> int:
        return len(self._chunks)

    @property
    def embedder_model(self) -> str:
        return self._embedder.model_id

    def _vector_top(self, query: str, k: int) -> list[tuple[int, float]]:
        if not self._chunks:
            return []
        query_vec = self._embedder.embed([query]).astype(np.float32)
        if query_vec.shape[0] == 0:
            return []
        bounded = min(k, self.size)
        distances, indices = self._faiss.search(query_vec, bounded)
        results: list[tuple[int, float]] = []
        for idx, score in zip(indices[0].tolist(), distances[0].tolist(), strict=False):
            if idx < 0:
                continue
            results.append((int(idx), float(score)))
        return results

    def _bm25_top(self, query: str, k: int) -> list[tuple[int, float]]:
        if not self._chunks or self._bm25 is None:
            return []
        tokens = _tokenize(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        order = np.argsort(-scores)[:k]
        return [(int(i), float(scores[int(i)])) for i in order if scores[int(i)] > 0.0]

    def query(
        self,
        text: str,
        *,
        top_k: int = 5,
        cluster_filter: list[str] | None = None,
        per_ranker_k: int = 20,
    ) -> list[RetrievalHit]:
        """Hybrid query: vector + BM25, fused with RRF, optionally filtered by cluster."""
        if not self._chunks or top_k <= 0 or not text.strip():
            return []

        vector_hits = self._vector_top(text, per_ranker_k)
        bm25_hits = self._bm25_top(text, per_ranker_k)

        rrf: dict[int, float] = {}
        vec_scores: dict[int, float] = {}
        lex_scores: dict[int, float] = {}
        for rank, (idx, score) in enumerate(vector_hits):
            rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (_RRF_K + rank + 1)
            vec_scores[idx] = score
        for rank, (idx, score) in enumerate(bm25_hits):
            rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (_RRF_K + rank + 1)
            lex_scores[idx] = score

        filter_set = {value for value in (cluster_filter or []) if value}
        ranked = sorted(rrf.items(), key=lambda pair: -pair[1])
        hits: list[RetrievalHit] = []
        for idx, fused in ranked:
            chunk = self._chunks[idx]
            cluster_hint = _cluster_value(chunk)
            if filter_set and cluster_hint not in filter_set:
                continue
            excerpt = chunk.text if len(chunk.text) <= 400 else chunk.text[:400] + "..."
            hits.append(
                RetrievalHit(
                    chunk_id=chunk.chunk_id,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    text_excerpt=excerpt,
                    score=fused,
                    vector_score=vec_scores.get(idx, 0.0),
                    bm25_score=lex_scores.get(idx, 0.0),
                    cluster_hint=cluster_hint,
                )
            )
            if len(hits) >= top_k:
                break
        return hits

    def save(self, base_dir: Path | None = None) -> Path:
        """Persist index files. Returns the directory used."""
        target = (base_dir or _DEFAULT_CACHE) / self._document_id
        target.mkdir(parents=True, exist_ok=True)
        manifest = {
            "version": _INDEX_VERSION,
            "document_id": self._document_id,
            "embedder_model": self._embedder.model_id,
            "dim": self._embedder.dim,
            "chunk_count": self.size,
            "hnsw": {"M": _HNSW_M, "efSearch": _HNSW_EF_SEARCH},
            "rrf_k": _RRF_K,
        }
        (target / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        with (target / "chunks.jsonl").open("w", encoding="utf-8") as handle:
            for chunk in self._chunks:
                handle.write(chunk.model_dump_json())
                handle.write("\n")
        faiss.write_index(self._faiss, str(target / "vectors.faiss"))
        return target

    @classmethod
    def load(
        cls,
        document_id: str,
        *,
        embedder: BaseEmbedder,
        base_dir: Path | None = None,
    ) -> TDRIndex:
        target = (base_dir or _DEFAULT_CACHE) / document_id
        manifest_path = target / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"No persisted index at {target}")
        manifest_any: Any = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = cast(dict[str, Any], manifest_any)
        if manifest.get("embedder_model") != embedder.model_id:
            raise ValueError(
                f"Embedder mismatch: stored {manifest.get('embedder_model')!r}, "
                f"got {embedder.model_id!r}"
            )
        if manifest.get("dim") != embedder.dim:
            raise ValueError("Embedder dim mismatch when loading TDRIndex")
        chunks: list[DocumentChunk] = []
        with (target / "chunks.jsonl").open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                chunks.append(DocumentChunk.model_validate_json(line))
        faiss_index = faiss.read_index(str(target / "vectors.faiss"))
        instance = cls.__new__(cls)
        instance._document_id = document_id
        instance._chunks = chunks
        instance._embedder = embedder
        instance._faiss = faiss_index
        instance._bm25 = BM25Okapi([_tokenize(c.text) for c in chunks]) if chunks else None
        return instance


__all__ = ["RetrievalHit", "TDRIndex"]
