"""Manual TDR ingestion helpers."""

from __future__ import annotations

import csv
import hashlib
from datetime import date
from pathlib import Path

from agenteperry.db.client import db
from agenteperry.tdr.models import TdrDocumentMetadata


def sync_to_db(records: list[TdrDocumentMetadata]) -> int:
    """Upsert TDR metadata records to the database. Returns count of upserted records."""
    query = """
        INSERT INTO tdr_documents (
            external_id, title, entity_name, source_url, file_url,
            procedure_code, sector, region, district, publication_date, estimated_value
        ) VALUES (
            %(external_id)s, %(title)s, %(entity_name)s, %(source_url)s, %(file_url)s,
            %(procedure_code)s, %(sector)s, %(region)s, %(district)s, %(publication_date)s, %(estimated_value)s
        )
        ON CONFLICT (external_id) DO UPDATE SET
            title = EXCLUDED.title,
            entity_name = EXCLUDED.entity_name,
            source_url = EXCLUDED.source_url,
            file_url = EXCLUDED.file_url,
            procedure_code = EXCLUDED.procedure_code,
            sector = EXCLUDED.sector,
            region = EXCLUDED.region,
            district = EXCLUDED.district,
            publication_date = EXCLUDED.publication_date,
            estimated_value = EXCLUDED.estimated_value,
            updated_at = now()
    """
    params_list = [record.model_dump() for record in records]
    # Remove local_path from params as it's not in the DB schema
    for p in params_list:
        p.pop("local_path", None)

    db.execute_batch(query, params_list)
    return len(records)


REQUIRED_COLUMNS = ["external_id", "title", "entity_name", "source_url", "file_url"]
OPTIONAL_COLUMNS = [
    "procedure_code",
    "sector",
    "region",
    "district",
    "publication_date",
    "estimated_value",
    "local_path",
]


def calculate_sha256(path: Path) -> str:
    """Calculate SHA256 without loading the full PDF into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for block in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manual_manifest(manifest_path: Path) -> list[TdrDocumentMetadata]:
    """Load and validate the MVP manual manifest CSV."""
    with manifest_path.open(newline="", encoding="utf-8") as file_obj:
        reader = csv.DictReader(file_obj)
        missing = sorted(set(REQUIRED_COLUMNS) - set(reader.fieldnames or []))
        if missing:
            raise ValueError(f"Manifest missing required columns: {', '.join(missing)}")

        records: list[TdrDocumentMetadata] = []
        for row in reader:
            records.append(
                TdrDocumentMetadata(
                    external_id=_clean_required(row, "external_id"),
                    title=_clean_required(row, "title"),
                    entity_name=_clean_required(row, "entity_name"),
                    source_url=_clean_required(row, "source_url"),
                    file_url=_clean_required(row, "file_url"),
                    procedure_code=_clean_optional(row.get("procedure_code")),
                    sector=_clean_optional(row.get("sector")),
                    region=_clean_optional(row.get("region")),
                    district=_clean_optional(row.get("district")),
                    publication_date=_clean_date(row.get("publication_date")),
                    estimated_value=_clean_float(row.get("estimated_value")),
                    local_path=_clean_local_path(manifest_path, row.get("local_path")),
                )
            )
    return records


def _clean_required(row: dict[str, str], column: str) -> str:
    value = _clean_optional(row.get(column))
    if not value:
        raise ValueError(f"Manifest row missing required column: {column}")
    return value


def _clean_optional(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _clean_date(value: str | None) -> date | None:
    cleaned = _clean_optional(value)
    return date.fromisoformat(cleaned) if cleaned else None


def _clean_float(value: str | None) -> float | None:
    cleaned = _clean_optional(value)
    return float(cleaned) if cleaned else None


def _clean_local_path(manifest_path: Path, value: str | None) -> Path | None:
    cleaned = _clean_optional(value)
    return (manifest_path.parent / cleaned).resolve() if cleaned else None
