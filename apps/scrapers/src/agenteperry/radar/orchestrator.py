"""Filesystem-backed radar orchestration for Activity 8A."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from agenteperry.collectors import CollectionResult, build_collector
from agenteperry.radar.cdc import (
    build_changeset,
    load_hash_index,
    save_hash_index,
    updated_hash_index,
)
from agenteperry.radar.models import ChangeSet, RadarRunResult, SourceRun
from agenteperry.sources import build_default_registry

_LOCAL_RECORD_FALLBACKS: dict[str, tuple[str, ...]] = {
    "ocds_peru": (
        "data/scraped/ocds/records.jsonl",
        "data/scraped/ocds/contracts_2026.jsonl",
    ),
    "sunat_padron": ("data/scraped/collectors/sunat_padron/records.jsonl",),
}

_COLLECTOR_INPUTS: dict[str, tuple[str, ...]] = {
    "ocds_peru": (
        "data/scraped/ocds/raw_2026.jsonl.gz",
        "data/scraped/ocds/records.jsonl",
    ),
    "sunat_padron": ("data/scraped/collectors/sunat_padron/records.jsonl",),
}


def run_source_radar(
    source_code: str,
    mode: str = "incremental",
    limit: int | None = None,
    analyze_docs: bool = False,
    base_dir: Path = Path("data/runs"),
) -> RadarRunResult:
    """Run generic CDC for a registered source and write auditable artifacts."""
    started_at = datetime.now(UTC)
    run_id = f"{source_code}_{started_at.strftime('%Y%m%dT%H%M%SZ')}"
    run_dir = base_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    source_run = SourceRun(
        run_id=run_id,
        source_code=source_code,
        mode=mode,
        status="running",
        started_at=started_at.isoformat(),
    )
    changes = ChangeSet(source_code=source_code, run_id=run_id)
    audit_path = run_dir / "audit.json"
    changed_records_path = run_dir / "changed_records.jsonl"
    manifest_path = run_dir / "run_manifest.json"
    hashes_path = base_dir / source_code / "hashes.json"

    try:
        registry = build_default_registry()
        source = registry.get(source_code)
        if source is None:
            raise ValueError(f"Unknown source: {source_code}")

        records = _collect_records(source_code=source_code, source=source, limit=limit, warnings=source_run.warnings)
        if limit is not None:
            records = records[:limit]

        existing_index = {} if mode == "full" else load_hash_index(source_code, base_dir=base_dir)
        changes = build_changeset(source_code, run_id, records, existing_index)
        hashes_path = save_hash_index(source_code, updated_hash_index(existing_index, changes), base_dir=base_dir)

        source_run.records_seen = changes.records_seen
        source_run.records_new = changes.records_new
        source_run.records_changed = changes.records_changed
        source_run.records_unchanged = changes.records_unchanged
        source_run.records_failed = changes.records_failed

        if analyze_docs:
            source_run.warnings.append("analyze_docs is a planned hook for Activity 8C; skipped in Activity 8A")

        _write_jsonl(changed_records_path, (record.to_dict() for record in changes.changed_records))
        _write_json(manifest_path, source_run.to_dict())
        source_run.status = "completed" if not source_run.errors else "partial"
    except Exception as exc:
        source_run.status = "failed"
        source_run.errors.append(str(exc))
        _write_jsonl(changed_records_path, [])
    finally:
        source_run.finished_at = datetime.now(UTC).isoformat()
        _write_json(manifest_path, source_run.to_dict())
        _write_json(
            audit_path,
            {
                "source_run": source_run.to_dict(),
                "changes": {
                    "source_code": changes.source_code,
                    "run_id": changes.run_id,
                    "records_seen": changes.records_seen,
                    "records_new": changes.records_new,
                    "records_changed": changes.records_changed,
                    "records_unchanged": changes.records_unchanged,
                    "records_failed": changes.records_failed,
                    "changed_records_count": len(changes.changed_records),
                    "failed_records_count": len(changes.failed_records),
                },
                "audit_path": str(audit_path),
                "changed_records_path": str(changed_records_path),
                "hashes_path": str(hashes_path),
            },
        )

    return RadarRunResult(
        source_run=source_run,
        changes=changes,
        audit_path=audit_path,
        changed_records_path=changed_records_path,
        hashes_path=hashes_path,
    )


def _collect_records(source_code: str, source: Any, limit: int | None, warnings: list[str]) -> list[dict[str, Any]]:
    try:
        collector = build_collector(source)
        input_path = _first_existing_path(_COLLECTOR_INPUTS.get(source_code, ()))
        if input_path is not None:
            results = collector.collect(input_path=input_path, limit=limit)
        else:
            results = collector.collect(limit=limit)
        return [_collection_result_to_record(result) for result in results]
    except Exception as exc:
        fallback = _first_existing_path(_LOCAL_RECORD_FALLBACKS.get(source_code, ()))
        if fallback is None:
            raise
        warnings.append(f"collector_failed_used_local_records_fallback: {exc}")
        return _read_jsonl_records(fallback, limit=limit)


def _collection_result_to_record(result: CollectionResult) -> dict[str, Any]:
    record = result.to_record()
    raw_data = record.get("raw_data")
    if isinstance(raw_data, dict):
        raw_dict = cast(dict[str, Any], raw_data)
        tender = raw_dict.get("tender")
        if isinstance(tender, dict):
            tender_dict = cast(dict[str, Any], tender)
            tender_docs = tender_dict.get("documents")
            if isinstance(tender_docs, list):
                record["documents"] = cast(list[Any], tender_docs)
    return record


def _read_jsonl_records(path: Path, limit: int | None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file_obj:
        for line in file_obj:
            if not line.strip():
                continue
            payload = cast(object, json.loads(line))
            if isinstance(payload, dict):
                records.append(cast(dict[str, Any], payload))
            if limit is not None and len(records) >= limit:
                break
    return records


def _first_existing_path(paths: Iterable[str]) -> Path | None:
    for path in paths:
        resolved = _resolve_repo_path(path)
        if resolved.exists():
            return resolved
    return None


def _resolve_repo_path(relative_path: str) -> Path:
    path = Path(relative_path)
    if path.exists():
        return path
    cwd = Path.cwd()
    for parent in (cwd, *cwd.parents):
        candidate = parent / relative_path
        if candidate.exists():
            return candidate
    return path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file_obj:
        for record in records:
            file_obj.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
