"""Thin Google Cloud Storage helpers — streaming reads only."""

from __future__ import annotations

import json
from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from google.cloud import storage  # type: ignore[import-untyped]

from agenteperry_api.config import get_settings


@lru_cache(maxsize=1)
def _client() -> storage.Client:
    settings = get_settings()
    return storage.Client(project=settings.gcp_project)


@lru_cache(maxsize=1)
def _bucket() -> storage.Bucket:
    settings = get_settings()
    return _client().bucket(settings.gcs_bucket)


def list_blobs(prefix: str, *, max_results: int | None = None) -> list[str]:
    """Return blob names under ``prefix`` (relative to the bucket root)."""
    iterator = _client().list_blobs(_bucket(), prefix=prefix)
    names: list[str] = []
    for blob in iterator:
        names.append(blob.name)
        if max_results is not None and len(names) >= max_results:
            break
    return names


def list_directories(prefix: str) -> list[str]:
    """Return immediate sub-directory names under ``prefix``."""
    iterator = _client().list_blobs(_bucket(), prefix=prefix, delimiter="/")
    # Consume to populate ``prefixes``.
    for _ in iterator:
        pass
    prefixes = getattr(iterator, "prefixes", [])
    return [p.rstrip("/").rsplit("/", 1)[-1] for p in prefixes]


def read_text(path: str) -> str | None:
    """Return blob contents as utf-8 text. ``None`` when missing."""
    blob = _bucket().blob(path)
    if not blob.exists(_client()):
        return None
    return blob.download_as_text(client=_client())


def read_json(path: str) -> Any | None:
    raw = read_text(path)
    if raw is None:
        return None
    return json.loads(raw)


def iter_jsonl(path: str, *, limit: int | None = None) -> Iterator[dict[str, Any]]:
    """Stream a JSONL blob line by line."""
    blob = _bucket().blob(path)
    if not blob.exists(_client()):
        return
    with blob.open("r", encoding="utf-8") as handle:
        for i, line in enumerate(handle):
            if not line.strip():
                continue
            yield json.loads(line)
            if limit is not None and i + 1 >= limit:
                return


def gcs_uri(path: str) -> str:
    return f"gs://{get_settings().gcs_bucket}/{path}"
