#!/usr/bin/env python3
"""Select validated SEACE Salud processes for the Golden Set."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


ELIGIBLE_DOCUMENT_TYPES = {"bases", "tdr", "bases_integradas"}


def select_golden_candidates(
    base_dir: Path = Path("data/scraped/seace_salud"),
    output_path: Path = Path("data/golden_set/metadata.csv"),
    *,
    min_text_coverage: float = 0.70,
) -> Path:
    """Write Golden Set metadata rows for analyzable Salud TDR processes."""
    processes = _read_csv(base_dir / "processes.csv")
    documents = _read_csv(base_dir / "documents.csv")
    awards = _read_csv(base_dir / "awards.csv", required=False)

    documents_by_process: dict[str, list[dict[str, str]]] = defaultdict(list)
    for document in documents:
        documents_by_process[document.get("process_id", "")].append(document)

    awards_by_process: dict[str, list[dict[str, str]]] = defaultdict(list)
    for award in awards:
        awards_by_process[award.get("process_id", "")].append(award)

    rows: list[dict[str, str]] = []
    for process in processes:
        process_id = process.get("process_id", "")
        if process.get("sector", "").strip().lower() != "salud":
            continue

        best_document = _best_eligible_document(
            documents_by_process.get(process_id, []), min_text_coverage=min_text_coverage
        )
        if best_document is None:
            continue

        award = _first_usable_award(awards_by_process.get(process_id, []))
        if award is None:
            continue

        rows.append(
            {
                "process_id": process_id,
                "ocid": process.get("ocid", ""),
                "seace_code": process.get("seace_code", ""),
                "entity_name": process.get("entity_name", ""),
                "entity_ruc": process.get("entity_ruc", ""),
                "supplier_name": award.get("supplier_name", ""),
                "supplier_ruc": award.get("supplier_ruc", ""),
                "document_id": best_document.get("document_id", ""),
                "document_type": best_document.get("document_type", ""),
                "file_path": best_document.get("file_path", ""),
                "text_coverage_ratio": best_document.get("text_coverage_ratio", ""),
                "award_source_page": award.get("award_source_page", ""),
                "source_url": process.get("source_url", ""),
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "process_id",
        "ocid",
        "seace_code",
        "entity_name",
        "entity_ruc",
        "supplier_name",
        "supplier_ruc",
        "document_id",
        "document_type",
        "file_path",
        "text_coverage_ratio",
        "award_source_page",
        "source_url",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def _best_eligible_document(
    documents: list[dict[str, str]], *, min_text_coverage: float
) -> dict[str, str] | None:
    eligible = [
        document
        for document in documents
        if document.get("document_type", "") in ELIGIBLE_DOCUMENT_TYPES
        and _float(document.get("text_coverage_ratio", "0")) >= min_text_coverage
        and document.get("parse_status", "") == "parsed"
    ]
    if not eligible:
        return None
    return sorted(
        eligible,
        key=lambda document: (
            document.get("document_type", "") != "bases_integradas",
            -_float(document.get("text_coverage_ratio", "0")),
        ),
    )[0]


def _first_usable_award(awards: list[dict[str, str]]) -> dict[str, str] | None:
    for award in awards:
        if (
            award.get("supplier_ruc", "").strip()
            and award.get("award_source_quote", "").strip()
            and award.get("award_source_page", "").strip()
        ):
            return award
    return None


def _read_csv(path: Path, *, required: bool = True) -> list[dict[str, str]]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file_obj:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(file_obj)]


def _float(value: str) -> float:
    try:
        return float(value.strip())
    except ValueError:
        return 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Select Golden Set candidates from SEACE Salud.")
    parser.add_argument("--base-dir", type=Path, default=Path("data/scraped/seace_salud"))
    parser.add_argument("--out", type=Path, default=Path("data/golden_set/metadata.csv"))
    parser.add_argument("--min-text-coverage", type=float, default=0.70)
    args = parser.parse_args()
    output = select_golden_candidates(
        args.base_dir,
        args.out,
        min_text_coverage=args.min_text_coverage,
    )
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
