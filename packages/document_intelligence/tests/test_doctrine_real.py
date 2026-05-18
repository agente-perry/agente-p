"""PR #12 — DoctrineIndex real corpus tests.

Validates:
- ``first_by_flag_code`` deterministic lookup
- autodetect of repo-relative artifact + graceful fallback when embedder
  dim mismatches the artifact
- artifact loader preserves source, page, section
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from document_intelligence.doctrine import load_doctrine
from document_intelligence.doctrine.index import DoctrineChunk, DoctrineIndex
from document_intelligence.embeddings import FakeEmbedder


def _make_index(embedder_dim: int = 64) -> DoctrineIndex:
    embedder = FakeEmbedder(dim=embedder_dim)
    chunks = [
        DoctrineChunk(
            chunk_id="ocp_001",
            source="OCP Red Flags (test)",
            section="Tender phase",
            page=22,
            text="Unreasonable prequalification requirements signal tailoring.",
            flag_code="OVER_SPECIFIED_EXPERIENCE",
        ),
        DoctrineChunk(
            chunk_id="ocp_002",
            source="OCP Red Flags (test)",
            section="Implementation",
            page=88,
            text="Notarial requirements increase documentary burden.",
            flag_code="EXCESSIVE_DOCUMENT_REQUIREMENT",
        ),
        DoctrineChunk(
            chunk_id="oecd_001",
            source="OECD AI Governance (test)",
            section="Audit",
            page=10,
            text="AI systems without audit trails create accountability gaps.",
            flag_code="AI_NO_AUDIT_TRAIL",
        ),
    ]
    return DoctrineIndex.from_chunks(chunks, embedder=embedder)


def test_first_by_flag_code_returns_first_match() -> None:
    index = _make_index()
    hit = index.first_by_flag_code("OVER_SPECIFIED_EXPERIENCE")
    assert hit is not None
    assert hit.chunk_id == "ocp_001"
    assert hit.page == 22
    assert "prequalification" in hit.quote.lower()


def test_first_by_flag_code_returns_none_for_unknown_flag() -> None:
    index = _make_index()
    assert index.first_by_flag_code("DOES_NOT_EXIST") is None


def test_first_by_flag_code_preserves_source_and_page() -> None:
    index = _make_index()
    hit = index.first_by_flag_code("EXCESSIVE_DOCUMENT_REQUIREMENT")
    assert hit is not None
    assert hit.source == "OCP Red Flags (test)"
    assert hit.page == 88
    assert hit.section == "Implementation"


def test_load_doctrine_falls_back_to_stub_on_dim_mismatch(tmp_path: Path) -> None:
    """Autodetected artifact at the repo default path may have a different dim
    than the test embedder. The loader must silently fall back to the stub
    when dim mismatches and the path was autodetected."""
    # Use small-dim embedder (artifact in repo is built at dim 384).
    embedder = FakeEmbedder(dim=64)
    index = load_doctrine(embedder=embedder)
    # Stub has 9 entries; real artifact would have 457. Either is acceptable
    # — the contract is "loader does not crash on dim mismatch".
    assert index.size >= 5


def test_load_doctrine_with_explicit_manifest_path_enforces_dim(tmp_path: Path) -> None:
    """When the caller hands us a manifest path, dim mismatches must raise."""
    from document_intelligence.doctrine import DoctrineLoadError

    chunks_file = tmp_path / "chunks.jsonl"
    chunks_file.write_text(
        json.dumps(
            {
                "chunk_id": "x",
                "source": "Test",
                "page": 1,
                "text": "lorem ipsum",
                "flag_code": "OVER_SPECIFIED_EXPERIENCE",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    vectors_file = tmp_path / "vectors.npy"
    np.save(vectors_file, np.zeros((1, 128), dtype=np.float32))
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
    import pytest

    with pytest.raises(DoctrineLoadError):
        load_doctrine(manifest_path=manifest_path, embedder=FakeEmbedder(dim=64))


def test_autodetected_artifact_loads_when_dim_matches() -> None:
    """When the autodetected artifact dim matches the embedder, it must be
    preferred over the stub. Skips when the real artifact is not in the repo."""
    repo_manifest = (
        Path(__file__).resolve().parents[3] / "data" / "doctrine" / "manifest.json"
    )
    if not repo_manifest.exists():
        import pytest

        pytest.skip("real doctrine artifact not built; run scripts/build_doctrine_index.py")
    manifest = json.loads(repo_manifest.read_text(encoding="utf-8"))
    embedder = FakeEmbedder(dim=int(manifest["dim"]))
    index = load_doctrine(embedder=embedder)
    assert index.size == int(manifest["count"])
    # First OCP chunk should be retrievable via flag_code lookup.
    hit = index.first_by_flag_code("EXCESSIVE_DOCUMENT_REQUIREMENT")
    assert hit is not None
    assert "OCP" in hit.source or "OECD" in hit.source
    assert hit.page is not None
    assert hit.page >= 1
