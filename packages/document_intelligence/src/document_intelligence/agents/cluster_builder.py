"""ClusterBuilderAgent — assign canonical cluster labels to chunks.

Contract (frozen): the agent MUST write ``chunk.metadata["cluster_label"]``
**before** ``TDRIndex`` is built or queried. The label is the value used by
``TDRIndex.query(..., cluster_filter=...)``.

Algorithm (mock mode):
    1. for each chunk, derive a normalized signal from ``section_hint`` first,
       then from the leading text of the chunk
    2. match the signal against ``flags/cluster_catalog.yaml`` keywords
    3. write the resolved label into ``chunk.metadata["cluster_label"]``
    4. group chunks by label into ``DocumentCluster`` records

The agent returns a NEW list of chunks plus the cluster list. The original
chunks are not mutated in place because they are Pydantic models.
"""

from __future__ import annotations

from collections import OrderedDict

from document_intelligence.agents._canonical import OTHERS_LABEL, match_cluster
from document_intelligence.schemas.chunk import DocumentChunk
from document_intelligence.schemas.cluster import DocumentCluster

_TEXT_PREVIEW_CHARS = 200


def _resolve_label(chunk: DocumentChunk) -> str:
    label = match_cluster(chunk.section_hint)
    if label != OTHERS_LABEL:
        return label
    return match_cluster(chunk.text[:_TEXT_PREVIEW_CHARS])


def _annotate(chunk: DocumentChunk, label: str) -> DocumentChunk:
    new_metadata = dict(chunk.metadata)
    new_metadata["cluster_label"] = label
    return chunk.model_copy(update={"metadata": new_metadata})


def build_clusters(
    chunks: list[DocumentChunk],
) -> tuple[list[DocumentChunk], list[DocumentCluster]]:
    """Annotate chunks with ``cluster_label`` and return both the labelled chunks and clusters."""
    if not chunks:
        return [], []
    labelled: list[DocumentChunk] = []
    grouped: OrderedDict[str, list[str]] = OrderedDict()
    for chunk in chunks:
        label = _resolve_label(chunk)
        annotated = _annotate(chunk, label)
        labelled.append(annotated)
        grouped.setdefault(label, []).append(annotated.chunk_id)
    clusters = [
        DocumentCluster(
            cluster_id=f"cluster::{index:02d}::{_slug(label)}",
            label=label,
            chunk_ids=chunk_ids,
        )
        for index, (label, chunk_ids) in enumerate(grouped.items())
    ]
    return labelled, clusters


def _slug(label: str) -> str:
    return "_".join(
        word.lower()
        for word in label.replace("/", " ").replace("-", " ").split()
        if word
    )


class ClusterBuilderAgent:
    """Thin OO wrapper around ``build_clusters``."""

    def __call__(
        self, chunks: list[DocumentChunk]
    ) -> tuple[list[DocumentChunk], list[DocumentCluster]]:
        return build_clusters(chunks)
