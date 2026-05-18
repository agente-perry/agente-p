"""Load the doctrinal corpus from an external artifact or from the stub YAML.

Artifact layout (collaborator-provided):

    data/doctrine/
      manifest.json     {version, model, dim, count, chunks_file, vectors_file}
      chunks.jsonl      one DoctrineChunk per line
      vectors.npy       float32 matrix [count, dim], rows L2-normalized

If the manifest file is missing, the loader falls back to the local stub at
``packages/document_intelligence/src/document_intelligence/flags/doctrine_stub.yaml``
and embeds it on the fly with the supplied embedder.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import numpy as np
import yaml

from document_intelligence.doctrine.index import DoctrineChunk, DoctrineIndex
from document_intelligence.embeddings import get_embedder
from document_intelligence.embeddings.base import BaseEmbedder

_DEFAULT_STUB_PATH = (
    Path(__file__).resolve().parent.parent / "flags" / "doctrine_stub.yaml"
)

# Repo-relative default manifest path. When ``load_doctrine`` is called
# without ``manifest_path`` and this file exists, the real corpus is
# preferred over the stub. Falls back to the stub when missing.
_REPO_DOCTRINE_DIR_CANDIDATES: tuple[Path, ...] = (
    Path.cwd() / "data" / "doctrine",
    Path(__file__).resolve().parents[5] / "data" / "doctrine",
)


def _autodetect_manifest() -> Path | None:
    for candidate in _REPO_DOCTRINE_DIR_CANDIDATES:
        manifest = candidate / "manifest.json"
        if manifest.exists():
            return manifest
    return None


class DoctrineLoadError(RuntimeError):
    """Raised when the doctrinal artifact cannot be parsed."""


def _load_stub_chunks(stub_path: Path) -> list[DoctrineChunk]:
    if not stub_path.exists():
        raise DoctrineLoadError(f"Doctrine stub not found at {stub_path}")
    raw_any: Any = yaml.safe_load(stub_path.read_text(encoding="utf-8")) or []
    raw = cast(list[dict[str, Any]], raw_any if isinstance(raw_any, list) else [])
    return [DoctrineChunk.model_validate(entry) for entry in raw]


def _load_artifact_chunks(chunks_path: Path) -> list[DoctrineChunk]:
    chunks: list[DoctrineChunk] = []
    with chunks_path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                payload: Any = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DoctrineLoadError(
                    f"{chunks_path}:{line_no} is not valid JSON: {exc}"
                ) from exc
            chunks.append(DoctrineChunk.model_validate(payload))
    return chunks


def load_doctrine(
    *,
    manifest_path: Path | None = None,
    stub_path: Path | None = None,
    embedder: BaseEmbedder | None = None,
) -> DoctrineIndex:
    """Return a ``DoctrineIndex``, preferring the artifact over the stub.

    When ``manifest_path`` is provided and exists, the loader trusts the
    artifact's vectors and bypasses the embedder for indexing.

    Otherwise it loads the stub YAML and embeds the entries with ``embedder``
    (defaults to the ``mock`` mode so local-first runs always succeed).
    """
    if embedder is None:
        embedder = get_embedder("mock")

    autodetected = False
    if manifest_path is None:
        manifest_path = _autodetect_manifest()
        autodetected = manifest_path is not None

    if manifest_path is not None and manifest_path.exists():
        try:
            manifest_any: Any = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DoctrineLoadError(f"Invalid manifest: {exc}") from exc
        manifest = cast(dict[str, Any], manifest_any)
        base = manifest_path.parent
        chunks_file = base / cast(str, manifest.get("chunks_file", "chunks.jsonl"))
        vectors_file = base / cast(str, manifest.get("vectors_file", "vectors.npy"))
        chunks = _load_artifact_chunks(chunks_file)
        vectors = np.load(vectors_file)
        if vectors.shape[0] != len(chunks):
            raise DoctrineLoadError(
                f"Vector count {vectors.shape[0]} does not match chunk count {len(chunks)}"
            )
        if vectors.shape[1] != embedder.dim:
            # When the caller explicitly handed us a manifest, fail loudly so
            # the embedder mismatch is visible. When we autodetected the
            # artifact (zero-config path used by tests), fall back to the stub
            # so a stub-sized embedder keeps working without ceremony.
            if not autodetected:
                raise DoctrineLoadError(
                    f"Artifact dim {vectors.shape[1]} does not match embedder dim "
                    f"{embedder.dim}. Use the same embedder model as the artifact, "
                    "or load the stub."
                )
        else:
            return DoctrineIndex(
                chunks, vectors.astype(np.float32, copy=False), embedder=embedder
            )

    stub = stub_path or _DEFAULT_STUB_PATH
    chunks = _load_stub_chunks(stub)
    return DoctrineIndex.from_chunks(chunks, embedder=embedder)
