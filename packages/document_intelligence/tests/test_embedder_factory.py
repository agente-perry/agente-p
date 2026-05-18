"""get_embedder factory: mode dispatch and error surfaces."""

from __future__ import annotations

import pytest

from document_intelligence.embeddings import (
    FakeEmbedder,
    OpenAIEmbedderError,
    get_embedder,
)


def test_get_embedder_mock_returns_fake() -> None:
    emb = get_embedder("mock", dim=128)
    assert isinstance(emb, FakeEmbedder)
    assert emb.dim == 128


def test_get_embedder_llm_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(OpenAIEmbedderError):
        get_embedder("llm")


def test_get_embedder_unknown_mode_raises() -> None:
    with pytest.raises(ValueError):
        get_embedder("not-a-mode")  # type: ignore[arg-type]
