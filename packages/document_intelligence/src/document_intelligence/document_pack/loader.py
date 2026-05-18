"""ProcessDocumentPack JSONL loader.

Reads packs delivered by the scraping team in JSONL (one pack per line)
or as individual JSON files. Validates each pack via ``validate_pack``;
invalid packs surface as ``(pack_or_none, errors)`` so callers can decide
whether to skip or abort.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from document_intelligence.document_pack.schemas import ProcessDocumentPack
from document_intelligence.document_pack.validator import validate_pack


def load_pack_from_json(path: Path) -> ProcessDocumentPack:
    """Load a single pack from a JSON file. Raises on schema violations."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ProcessDocumentPack.model_validate(payload)


def iter_packs_from_jsonl(
    path: Path,
    *,
    check_file_existence: bool = False,
) -> Iterator[tuple[ProcessDocumentPack | None, list[str]]]:
    """Yield ``(pack | None, errors)`` per line.

    A line that fails Pydantic validation yields ``(None, [str(exc)])``.
    A line that is parseable but fails pack-level invariants yields
    ``(pack, errors)``. A clean line yields ``(pack, [])``.
    """
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                payload = json.loads(line)
                pack = ProcessDocumentPack.model_validate(payload)
            except Exception as exc:  # noqa: BLE001 — propagate as validation error
                yield None, [f"line {line_no}: {exc}"]
                continue
            errs = validate_pack(pack, check_file_existence=check_file_existence)
            yield pack, errs


def load_valid_packs_from_jsonl(
    path: Path,
    *,
    check_file_existence: bool = False,
    skip_invalid: bool = True,
) -> tuple[list[ProcessDocumentPack], list[tuple[int, list[str]]]]:
    """Return ``(valid_packs, [(line_no, errors)...])``.

    When ``skip_invalid=False``, raises ``ValueError`` on the first
    validation failure.
    """
    valid: list[ProcessDocumentPack] = []
    rejected: list[tuple[int, list[str]]] = []
    for line_no, (pack, errs) in enumerate(
        iter_packs_from_jsonl(path, check_file_existence=check_file_existence),
        start=1,
    ):
        if pack is None or errs:
            rejected.append((line_no, errs))
            if not skip_invalid:
                raise ValueError(
                    f"pack at line {line_no} failed validation:\n  - "
                    + "\n  - ".join(errs)
                )
            continue
        valid.append(pack)
    return valid, rejected
