"""Embedding input preparation.

Embeddings support search. They do not decide risk or score.
"""

from __future__ import annotations

from agenteperry.tdr.models import TdrChunk, TdrEmbeddingInput


def build_embedding_inputs(chunks: list[TdrChunk], *, embedding_model: str = "text-embedding-3-small") -> list[TdrEmbeddingInput]:
    """Create provider-ready embedding payloads from chunks."""
    return [
        TdrEmbeddingInput(chunk_index=chunk.chunk_index, text=chunk.text, embedding_model=embedding_model)
        for chunk in chunks
        if chunk.text.strip()
    ]
