#!/usr/bin/env python3
"""Read-only data reality audit for AgentePerry.

This script does not write to the database, does not download files, and does
not run OCR. It reports what data exists, where it appears to come from, and
which paths look like tests/fixtures/sample/tmp data.

Usage:
    cd apps/scrapers && uv run python ../../scripts/audit_data_reality.py
    cd apps/scrapers && DATABASE_URL=... uv run python ../../scripts/audit_data_reality.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRAPERS_SRC = REPO_ROOT / "apps" / "scrapers" / "src"
sys.path.insert(0, str(SCRAPERS_SRC))

from agenteperry.db.client import DbClient  # noqa: E402

SUSPICIOUS_PATTERNS = ("tests/", "fixtures/", "sample", "/tmp/", "_test_", "dummy")
OCID_PATTERN = re.compile(r"ocds[-_][a-z0-9]+[-_][a-z0-9]+[-_][a-z0-9_\-]+", re.IGNORECASE)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only AgentePerry data reality audit.")
    parser.add_argument("--data-dir", type=Path, default=REPO_ROOT / "data")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    report: dict[str, Any] = {
        "repo_root": str(REPO_ROOT),
        "data_dir": str(args.data_dir),
        "database": audit_database(),
        "disk": audit_disk(args.data_dir),
        "suspicious_code_paths": audit_code_paths(),
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print_report(report)
    return 0


def audit_database() -> dict[str, Any]:
    if not os.environ.get("DATABASE_URL"):
        return {"available": False, "error": "DATABASE_URL is not set"}

    db = DbClient()
    report: dict[str, Any] = {"available": True, "errors": []}

    report["source_records_by_type"] = count_grouped(
        db,
        "source_records",
        "record_type",
        "SELECT record_type, COUNT(*) AS count FROM source_records GROUP BY record_type ORDER BY count DESC",
    )
    report["source_entities_by_type"] = count_grouped(
        db,
        "source_entities",
        "entity_type",
        "SELECT entity_type, COUNT(*) AS count FROM source_entities GROUP BY entity_type ORDER BY count DESC",
    )
    report["tdr_counts"] = {
        "tdr_documents": count_table(db, "tdr_documents"),
        "tdr_chunks": count_table(db, "tdr_chunks"),
        "tdr_flags": count_table(db, "tdr_flags"),
    }
    report["sunat_coverage"] = query_one(
        db,
        """
        SELECT
            COUNT(*) FILTER (WHERE metadata->>'sunat_razon_social' IS NOT NULL) AS companies_with_sunat,
            COUNT(*) FILTER (WHERE metadata->>'sunat_razon_social' IS NULL) AS companies_without_sunat,
            COUNT(*) AS companies_total
        FROM source_entities
        WHERE entity_type = 'company'
        """,
    )
    coverage = report["sunat_coverage"]
    if coverage and coverage.get("companies_total"):
        total = int(coverage["companies_total"])
        enriched = int(coverage.get("companies_with_sunat") or 0)
        coverage["coverage_pct"] = round(enriched / total * 100, 4) if total else 0.0

    report["enriched_raw_paths"] = query_all(
        db,
        """
        SELECT COALESCE(metadata->>'raw_path', 'NULL') AS raw_path, COUNT(*) AS count
        FROM source_entities
        WHERE entity_type = 'company'
          AND metadata->>'sunat_razon_social' IS NOT NULL
        GROUP BY COALESCE(metadata->>'raw_path', 'NULL')
        ORDER BY count DESC
        LIMIT 25
        """,
    )
    report["suspicious_db_paths"] = suspicious_db_paths(db)
    report["tdrs_linked_to_ocid"] = tdr_ocid_linkage(db)
    return report


def count_grouped(db: DbClient, table: str, key: str, query: str) -> dict[str, int]:
    if not table_exists(db, table):
        return {}
    rows = query_all(db, query)
    return {str(row.get(key) or "NULL"): int(row.get("count") or 0) for row in rows}


def count_table(db: DbClient, table: str) -> int | None:
    if not table_exists(db, table):
        return None
    row = query_one(db, f"SELECT COUNT(*) AS count FROM {table}")
    return int(row.get("count") or 0) if row else 0


def table_exists(db: DbClient, table: str) -> bool:
    rows = db.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table,),
    )
    return bool(rows)


def column_exists(db: DbClient, table: str, column: str) -> bool:
    rows = db.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    return bool(rows)


def query_one(db: DbClient, query: str) -> dict[str, Any]:
    rows = query_all(db, query)
    return rows[0] if rows else {}


def query_all(db: DbClient, query: str) -> list[dict[str, Any]]:
    try:
        return db.execute(query)
    except Exception as exc:  # pragma: no cover - audit must degrade gracefully
        return [{"error": str(exc)}]


def suspicious_db_paths(db: DbClient) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if table_exists(db, "source_records") and column_exists(db, "source_records", "raw_path"):
        rows.extend(query_all(
            db,
            """
            SELECT 'source_records.raw_path' AS location, raw_path AS path, COUNT(*) AS count
            FROM source_records
            WHERE raw_path IS NOT NULL
              AND (
                lower(raw_path) LIKE '%tests/%'
                OR lower(raw_path) LIKE '%fixtures/%'
                OR lower(raw_path) LIKE '%sample%'
                OR lower(raw_path) LIKE '%/tmp/%'
                OR lower(raw_path) LIKE '%_test_%'
                OR lower(raw_path) LIKE '%dummy%'
              )
            GROUP BY raw_path
            ORDER BY count DESC
            LIMIT 50
            """,
        ))
    if table_exists(db, "source_entities") and column_exists(db, "source_entities", "metadata"):
        rows.extend(query_all(
            db,
            """
            SELECT 'source_entities.metadata.raw_path' AS location, metadata->>'raw_path' AS path, COUNT(*) AS count
            FROM source_entities
            WHERE metadata->>'raw_path' IS NOT NULL
              AND (
                lower(metadata->>'raw_path') LIKE '%tests/%'
                OR lower(metadata->>'raw_path') LIKE '%fixtures/%'
                OR lower(metadata->>'raw_path') LIKE '%sample%'
                OR lower(metadata->>'raw_path') LIKE '%/tmp/%'
                OR lower(metadata->>'raw_path') LIKE '%_test_%'
                OR lower(metadata->>'raw_path') LIKE '%dummy%'
              )
            GROUP BY metadata->>'raw_path'
            ORDER BY count DESC
            LIMIT 50
            """,
        ))
    return rows


def tdr_ocid_linkage(db: DbClient) -> dict[str, Any]:
    if not table_exists(db, "tdr_documents"):
        return {"available": False, "reason": "tdr_documents table does not exist"}
    link_column = None
    for candidate in ("ocid", "external_id"):
        if column_exists(db, "tdr_documents", candidate):
            link_column = candidate
            break
    if link_column is None:
        return {"available": False, "reason": "tdr_documents has no ocid/external_id column"}
    return query_one(
        db,
        f"""
        SELECT
            COUNT(*) AS total_tdr_documents,
            COUNT(*) FILTER (WHERE {link_column} IS NOT NULL) AS tdrs_with_link_value,
            COUNT(*) FILTER (
                WHERE EXISTS (
                    SELECT 1 FROM source_records sr
                    WHERE sr.external_id = tdr_documents.{link_column}
                      AND sr.record_type = 'contract'
                )
            ) AS tdrs_matching_source_records
        FROM tdr_documents
        """,
    )


def audit_disk(data_dir: Path) -> dict[str, Any]:
    pdfs = sorted(data_dir.rglob("*.pdf")) if data_dir.exists() else []
    by_dir: Counter[str] = Counter(str(path.parent.relative_to(REPO_ROOT)) for path in pdfs)
    total_bytes = sum(path.stat().st_size for path in pdfs if path.exists())
    top_largest = sorted(
        (
            {"path": str(path.relative_to(REPO_ROOT)), "bytes": path.stat().st_size, "ocid": extract_ocid(path)}
            for path in pdfs
            if path.exists()
        ),
        key=lambda item: int(item["bytes"]),
        reverse=True,
    )[:20]
    suspicious = [str(path.relative_to(REPO_ROOT)) for path in pdfs if is_suspicious(str(path))]
    identifiable = sum(1 for path in pdfs if extract_ocid(path))
    return {
        "data_dir_exists": data_dir.exists(),
        "total_pdfs": len(pdfs),
        "pdfs_with_identifiable_ocid": identifiable,
        "pdfs_without_identifiable_ocid": len(pdfs) - identifiable,
        "total_bytes": total_bytes,
        "pdfs_by_directory": dict(by_dir.most_common()),
        "top_largest_pdfs": top_largest,
        "suspicious_pdf_paths": suspicious[:100],
    }


def audit_code_paths() -> dict[str, Any]:
    matches: dict[str, list[str]] = defaultdict(list)
    for base in (REPO_ROOT / "apps" / "scrapers", REPO_ROOT / "scripts"):
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if ".venv" in path.parts or "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in SUSPICIOUS_PATTERNS:
                if pattern in text.lower():
                    matches[str(path.relative_to(REPO_ROOT))].append(pattern)
    return {path: sorted(set(patterns)) for path, patterns in sorted(matches.items())}


def is_suspicious(value: str) -> bool:
    lowered = value.lower().replace("\\", "/")
    return any(pattern in lowered for pattern in SUSPICIOUS_PATTERNS)


def extract_ocid(path: Path) -> str | None:
    normalized = str(path).replace("_", "-")
    match = OCID_PATTERN.search(normalized)
    return match.group(0) if match else None


def print_report(report: dict[str, Any]) -> None:
    print("=" * 78)
    print("AGENTEPERRY DATA REALITY AUDIT (READ-ONLY)")
    print("=" * 78)
    db = report["database"]
    print("\n## Database")
    if not db.get("available"):
        print(f"  unavailable: {db.get('error')}")
    else:
        print("  source_records by record_type:")
        for key, value in db.get("source_records_by_type", {}).items():
            print(f"    {key:20s} {value:>10,}")
        print("  source_entities by entity_type:")
        for key, value in db.get("source_entities_by_type", {}).items():
            print(f"    {key:20s} {value:>10,}")
        print("  TDR counts:")
        for key, value in db.get("tdr_counts", {}).items():
            print(f"    {key:20s} {value if value is not None else 'missing'}")
        coverage = db.get("sunat_coverage") or {}
        print("  SUNAT coverage:")
        print(f"    companies_total       {coverage.get('companies_total', 0):>10,}")
        print(f"    companies_with_sunat  {coverage.get('companies_with_sunat', 0):>10,}")
        print(f"    coverage_pct          {coverage.get('coverage_pct', 0)}%")
        print("  enriched raw_path origins:")
        for row in db.get("enriched_raw_paths", []):
            print(f"    {row.get('count', 0):>8}  {row.get('raw_path')}")
        print("  suspicious DB paths:")
        suspicious_paths = db.get("suspicious_db_paths", [])
        if suspicious_paths:
            for row in suspicious_paths:
                print(f"    {row.get('count', 0):>8}  {row.get('location')}: {row.get('path')}")
        else:
            print("    none found by pattern")
        print("  TDR linkage:")
        print(f"    {db.get('tdrs_linked_to_ocid')}")

    disk = report["disk"]
    print("\n## Disk PDFs")
    print(f"  data_dir_exists             {disk['data_dir_exists']}")
    print(f"  total_pdfs                  {disk['total_pdfs']:,}")
    print(f"  pdfs_with_identifiable_ocid {disk['pdfs_with_identifiable_ocid']:,}")
    print(f"  total_bytes                 {disk['total_bytes']:,}")
    print("  PDFs by directory:")
    for directory, count in list(disk["pdfs_by_directory"].items())[:20]:
        print(f"    {count:>8,}  {directory}")
    print("  suspicious PDF paths:")
    if disk["suspicious_pdf_paths"]:
        for path in disk["suspicious_pdf_paths"][:20]:
            print(f"    {path}")
    else:
        print("    none found by pattern")

    print("\n## Suspicious Code Path References")
    code_matches = report["suspicious_code_paths"]
    if code_matches:
        for path, patterns in code_matches.items():
            print(f"  {path}: {', '.join(patterns)}")
    else:
        print("  none found by pattern")


if __name__ == "__main__":
    raise SystemExit(main())
