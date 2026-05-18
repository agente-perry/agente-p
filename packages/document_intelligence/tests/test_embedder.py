"""FakeEmbedder is deterministic, normalized, and shape-correct."""

from __future__ import annotations

import numpy as np
import pytest

from document_intelligence.embeddings import FakeEmbedder, get_default_embedder


def test_fake_embedder_is_deterministic() -> None:
    emb = FakeEmbedder(dim=128)
    a = emb.embed(["entregables formato A3"])
    b = emb.embed(["entregables formato A3"])
    assert np.array_equal(a, b)


def test_fake_embedder_shape_and_norm() -> None:
    emb = FakeEmbedder(dim=64)
    matrix = emb.embed(["uno", "dos", "tres palabras juntas"])
    assert matrix.shape == (3, 64)
    norms = np.linalg.norm(matrix, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)


def test_fake_embedder_zero_for_empty_text() -> None:
    emb = FakeEmbedder(dim=64)
    matrix = emb.embed([""])
    assert matrix.shape == (1, 64)
    assert np.linalg.norm(matrix[0]) == 0.0


def test_fake_embedder_distinguishes_distinct_inputs() -> None:
    emb = FakeEmbedder(dim=128)
    matrix = emb.embed(["entregables fisicos impresos", "criterios subjetivos de comite"])
    similarity = float(matrix[0] @ matrix[1])
    assert similarity < 0.99


def test_fake_embedder_rejects_tiny_dim() -> None:
    with pytest.raises(ValueError):
        FakeEmbedder(dim=4)


def test_default_embedder_factory() -> None:
    emb = get_default_embedder(dim=128)
    assert emb.dim == 128
    assert emb.model_id == "fake-deterministic-v1"
