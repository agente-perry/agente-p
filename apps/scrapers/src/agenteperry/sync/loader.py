"""Sync collectors' JSONL output to Supabase/Postgres.

Two-stage pipeline:
  1. collect → *_records.jsonl   (source_records)
  2. map     → *_graph.json       (source_entities + source_relationships)

This module handles stage 3: upserting those outputs into the real database.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from agenteperry.db.client import DbClient

db = DbClient()

_SOURCE_CODE_CACHE: dict[str, str] = {}

FORBIDDEN_PATH_PATTERNS = [
    "tests/",
    "fixtures/",
    "/tmp/",
    "_test_",
    "sample/",
    ".sample",
]

PRODUCTION_GUARD_ENABLED = os.environ.get("AGENTEERRY_PRODUCTION_GUARD", "1") == "1"


def _check_production_guard(raw_path: str | None, allow_fixture: bool = False) -> None:
    """Raise ValueError if raw_path looks like test/fixture data."""
    if not PRODUCTION_GUARD_ENABLED or allow_fixture:
        return
    if raw_path is None:
        return
    path_lower = raw_path.lower()
    for pattern in FORBIDDEN_PATH_PATTERNS:
        if pattern in path_lower:
            raise ValueError(
                f"\n  PRODUCTION GUARD: path '{raw_path}'\n"
                f"  contains '{pattern}' — indicates test/fixture data.\n"
                f"  NOT allowed in production pipeline.\n"
                f"  Use --allow-fixture only for test runs.\n"
            )


def _resolve_source_id(source_code: str) -> str:
    if source_code not in _SOURCE_CODE_CACHE:
        rows = db.execute(
            "SELECT id FROM source_catalog WHERE source_code = %s",
            (source_code,),
        )
        if not rows:
            raise ValueError(f"source_code {source_code!r} not found in source_catalog")
        _SOURCE_CODE_CACHE[source_code] = str(rows[0]["id"])
    return _SOURCE_CODE_CACHE[source_code]


def upsert_source_records(records_jsonl: Path, batch_size: int = 500, allow_fixture: bool = False) -> int:
    """Upsert source_records from a JSONL file exported by ``sources collect``."""
    rows = _load_jsonl(records_jsonl)
    if not rows:
        return 0

    raw_path = rows[0].get("raw_path") if rows else None
    _check_production_guard(raw_path, allow_fixture=allow_fixture)

    all_columns = list({k for row in rows for k in row.keys()})
    params_list: list[dict[str, Any]] = []
    for row in rows:
        normalized = _normalize_record(row)
        source_code = normalized.pop("source_code", None)
        if source_code:
            normalized["source_id"] = _resolve_source_id(source_code)
        for col in all_columns:
            normalized.setdefault(col, None)
        params_list.append(normalized)

    columns = ["source_id"] + [c for c in all_columns if c != "source_code"]
    query = _make_upsert_sql("source_records", columns, on_conflict="external_id")

    total = 0
    for start in range(0, len(params_list), batch_size):
        batch = params_list[start : start + batch_size]
        db.execute_batch(query, batch)
        total += len(batch)

    return total


def upsert_entities(graph_json: Path, batch_size: int = 500, allow_fixture: bool = False) -> int:
    """Upsert source_entities from a graph JSON exported by ``graph map-records``."""
    raw = json.loads(graph_json.read_text(encoding="utf-8"))
    entities = cast(list[dict[str, Any]], raw.get("entities", []))
    if not entities:
        return 0

    first_path = entities[0].get("metadata", {}).get("raw_path") if entities else None
    _check_production_guard(first_path, allow_fixture=allow_fixture)

    params_list: list[dict[str, Any]] = [
        {
            "entity_type": e["entity_type"],
            "canonical_id": e["canonical_id"],
            "display_name": e["display_name"],
            "metadata": json.dumps(e.get("metadata", {})),
            "sources": e.get("sources", []),
        }
        for e in entities
    ]
    columns = list(params_list[0].keys())
    query = _make_upsert_sql("source_entities", columns, on_conflict="canonical_id")

    total = 0
    for start in range(0, len(params_list), batch_size):
        batch = params_list[start : start + batch_size]
        db.execute_batch(query, batch)
        total += len(batch)

    return total


def upsert_relationships(graph_json: Path, batch_size: int = 500) -> int:
    """Upsert source_relationships from a graph JSON exported by ``graph map-records``."""
    raw = json.loads(graph_json.read_text(encoding="utf-8"))
    rels = cast(list[dict[str, Any]], raw.get("relationships", []))
    if not rels:
        return 0

    canonical_ids = list({r["source_canonical_id"] for r in rels} | {r["target_canonical_id"] for r in rels})
    id_rows = db.execute(
        "SELECT id, canonical_id FROM source_entities WHERE canonical_id = ANY(%s)",
        (canonical_ids,),
    )
    canon_to_uuid = {row["canonical_id"]: row["id"] for row in id_rows}

    params_list: list[dict[str, Any]] = []
    for r in rels:
        source_uuid = canon_to_uuid.get(r["source_canonical_id"])
        target_uuid = canon_to_uuid.get(r["target_canonical_id"])
        if source_uuid is None or target_uuid is None:
            continue
        params_list.append({
            "source_id": source_uuid,
            "target_id": target_uuid,
            "rel_type": r["rel_type"],
            "properties": json.dumps(r.get("properties", {})),
            "data_source": r.get("data_source"),
        })

    if not params_list:
        return 0

    columns = list(params_list[0].keys())
    query = _make_upsert_sql("source_relationships", columns, on_conflict="source_id,target_id,rel_type")

    total = 0
    for start in range(0, len(params_list), batch_size):
        batch = params_list[start : start + batch_size]
        db.execute_batch(query, batch)
        total += len(batch)

    return total


def merge_sunat_metadata(
    existing: dict[str, Any],
    sunat_record: dict[str, Any],
    now_iso: str,
) -> dict[str, Any]:
    """Merge SUNAT metadata into an existing company entity non-destructively.

    Preserves ``display_name`` and existing metadata. Adds SUNAT fields
    under ``sunat_*`` keys.
    """
    raw_meta = existing.get("metadata", {})
    if isinstance(raw_meta, str):
        metadata: dict[str, Any] = json.loads(raw_meta) if raw_meta else {}
    elif isinstance(raw_meta, dict):
        metadata = cast(dict[str, Any], raw_meta)
    else:
        metadata = {}

    # Preserve OCDS name if not already captured
    if "ocds_name" not in metadata:
        metadata["ocds_name"] = existing.get("display_name")

    parsed_data = sunat_record.get("parsed_data", {})
    metadata["sunat_razon_social"] = sunat_record.get("entity_name")
    metadata["sunat_estado"] = parsed_data.get("estado")
    metadata["sunat_condicion"] = parsed_data.get("condicion")
    metadata["sunat_ubigeo"] = parsed_data.get("ubigeo")
    metadata["sunat_domicilio_fiscal"] = parsed_data.get("domicilio_fiscal")
    metadata["sunat_last_seen_at"] = now_iso

    existing_sources = existing.get("sources", [])
    if isinstance(existing_sources, str):
        existing_sources = json.loads(existing_sources)
    sources = sorted(set(cast(list[str], existing_sources) + ["sunat_padron"]))

    return {
        "id": existing["id"],
        "metadata": json.dumps(metadata),
        "sources": sources,
    }


def enrich_companies_from_sunat(records_jsonl: Path, batch_size: int = 500) -> dict[str, int]:
    """Enrich existing ``source_entities`` companies with SUNAT metadata.

    Reads a ``records.jsonl`` produced by ``sources collect sunat_padron``,
    finds matching companies by RUC, and updates metadata non-destructively.
    """
    from datetime import datetime, timezone

    records = _load_jsonl(records_jsonl)

    # Filter to valid SUNAT records with 11-digit RUC
    sunat_records: list[dict[str, Any]] = []
    for row in records:
        if row.get("source_code") != "sunat_padron":
            continue
        ruc = row.get("entity_ruc")
        if not ruc or len(str(ruc)) != 11:
            continue
        sunat_records.append(row)

    if not sunat_records:
        return {
            "companies_seen": 0,
            "companies_enriched": 0,
            "companies_unmatched": 0,
            "records_skipped": len(records) - len(sunat_records),
            "errors": 0,
        }

    rucs = [cast(str, r["entity_ruc"]) for r in sunat_records]
    now_iso = datetime.now(timezone.utc).isoformat()  # noqa: UP017

    id_rows = db.execute(
        "SELECT id, canonical_id, display_name, metadata, sources "
        "FROM source_entities WHERE entity_type = 'company' AND canonical_id = ANY(%s)",
        (rucs,),
    )
    existing_by_ruc = {str(r["canonical_id"]): dict(r) for r in id_rows}

    enriched = 0
    unmatched = 0
    errors = 0

    updates: list[dict[str, Any]] = []
    for record in sunat_records:
        ruc = cast(str, record["entity_ruc"])
        existing = existing_by_ruc.get(ruc)
        if existing is None:
            unmatched += 1
            continue
        try:
            merged = merge_sunat_metadata(existing, record, now_iso)
            updates.append(merged)
            enriched += 1
        except Exception:
            errors += 1
            continue

    # Batch update
    if updates:
        query = (
            "UPDATE source_entities SET metadata = %(metadata)s, sources = %(sources)s "
            "WHERE id = %(id)s"
        )
        for start in range(0, len(updates), batch_size):
            batch = updates[start : start + batch_size]
            db.execute_batch(query, batch)

    return {
        "companies_seen": len(sunat_records),
        "companies_enriched": enriched,
        "companies_unmatched": unmatched,
        "records_skipped": len(records) - len(sunat_records),
        "errors": errors,
    }


def _make_upsert_sql(table: str, columns: list[str], on_conflict: str) -> str:
    """Generate a parameterized ON CONFLICT upsert statement."""
    col_list = ", ".join(columns)
    val_placeholder = ", ".join(f"%({col})s" for col in columns)
    set_clause = ", ".join(f"{col} = EXCLUDED.{col}" for col in columns)
    return f"INSERT INTO {table} ({col_list}) VALUES ({val_placeholder}) ON CONFLICT ({on_conflict}) DO UPDATE SET {set_clause}"


def _normalize_record(row: Mapping[str, Any]) -> dict[str, Any]:
    """Clean a CollectionResult dict for DB upsert."""
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        if value is None:
            continue
        if key in ("raw_data", "parsed_data", "metadata"):
            normalized[key] = json.dumps(value)
        elif key in ("sources", "fields", "red_flags"):
            normalized[key] = json.dumps(value) if isinstance(value, list) else value
        elif key == "fecha" and value:
            normalized[key] = str(value)
        elif key in ("monto", "estimated_value") and value is not None:
            try:
                normalized[key] = float(value)
            except (ValueError, TypeError):
                normalized[key] = value
        else:
            normalized[key] = value
    return normalized


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            records.append(json.loads(stripped))
    return records


def run_full_sync(
    records_jsonl: Path,
    graph_json: Path | None = None,
) -> dict[str, int]:
    """Run the complete sync pipeline: records then entities then relationships."""
    counts: dict[str, int] = {}
    if records_jsonl.exists():
        counts["source_records"] = upsert_source_records(records_jsonl)
    if graph_json and graph_json.exists():
        counts["source_entities"] = upsert_entities(graph_json)
        counts["source_relationships"] = upsert_relationships(graph_json)
    return counts
