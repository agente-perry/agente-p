"""DoctrineLoader: stub fallback, manifest artifact, query shape."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from document_intelligence.doctrine import DoctrineLoadError, load_doctrine
from document_intelligence.embeddings import FakeEmbedder


def test_load_stub_when_manifest_missing() -> None:
    index = load_doctrine(manifest_path=Path("/nonexistent/manifest.json"))
    assert index.size >= 5
    assert index.embedder_model.startswith("fake-")


def test_stub_query_returns_doctrine_hits() -> None:
    embedder = FakeEmbedder(dim=128)
    index = load_doctrine(embedder=embedder)
    hits = index.query("informe impreso formato fisico sin dataset", top_k=3)
    assert hits
    flag_codes = {h.flag_code for h in hits}
    assert any(code is not None for code in flag_codes)
    for hit in hits:
        assert hit.source
        assert hit.quote


def test_load_from_artifact(tmp_path: Path) -> None:
    embedder = FakeEmbedder(dim=64)
    entries = [
        {
            "chunk_id": "art.001",
            "source": "Artifact Source",
            "section": "Phase A",
            "page": 1,
            "text": "Test doctrine entry one.",
            "flag_code": "TEST_FLAG_A",
        },
        {
            "chunk_id": "art.002",
            "source": "Artifact Source",
            "section": "Phase B",
            "page": 2,
            "text": "Different doctrine entry text.",
            "flag_code": "TEST_FLAG_B",
        },
    ]
    chunks_path = tmp_path / "chunks.jsonl"
    chunks_path.write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")
    vectors = embedder.embed([e["text"] for e in entries])
    vectors_path = tmp_path / "vectors.npy"
    np.save(vectors_path, vectors)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "model": "fake-deterministic-v1",
                "dim": 64,
                "count": 2,
                "chunks_file": "chunks.jsonl",
                "vectors_file": "vectors.npy",
            }
        ),
        encoding="utf-8",
    )
    index = load_doctrine(manifest_path=manifest_path, embedder=embedder)
    assert index.size == 2
    hits = index.query("Different doctrine entry", top_k=2)
    assert hits[0].chunk_id == "art.002"


def test_artifact_rejects_dim_mismatch(tmp_path: Path) -> None:
    embedder = FakeEmbedder(dim=64)
    chunks_path = tmp_path / "chunks.jsonl"
    chunks_path.write_text(
        json.dumps({"chunk_id": "x", "source": "s", "text": "t"}) + "\n",
        encoding="utf-8",
    )
    np.save(tmp_path / "vectors.npy", np.zeros((1, 128), dtype=np.float32))
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "dim": 128,
                "count": 1,
                "chunks_file": "chunks.jsonl",
                "vectors_file": "vectors.npy",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(DoctrineLoadError):
        load_doctrine(manifest_path=manifest_path, embedder=embedder)
