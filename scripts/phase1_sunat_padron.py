#!/usr/bin/env python3
"""Download and parse SUNAT Padrón Reducido (14.5M RUCs) for enrichment.

Downloads www2.sunat.gob.pe/padron_reducido_ruc.zip, parses pipe-delimited TXT
with ISO-8859-1 encoding, and writes a filtered CSV containing only the RUCs
that appear in the OCDS awards (supplier_ruc from processes.csv).

Usage:
    python scripts/phase1_sunat_padron.py --output-dir data/sunat --limit 100000
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Iterator

SCRIPT_VERSION = "1.0.0"
SUNAT_ZIP_URL = "http://www2.sunat.gob.pe/padron_reducido_ruc.zip"

SUNAT_COLUMNS = [
    "ruc",
    "razon_social",
    "estado",
    "condicion",
    "ubigeo",
    "tipo_via",
    "nombre_via",
    "codigo_zona",
    "tipo_zona",
    "numero",
    "interior",
    "lote",
    "departamento",
    "manzana",
    "kilometro",
]


def normalize_ruc(value: str | None) -> str | None:
    digits = "".join(ch for ch in (value or "").strip() if ch.isdigit())
    return digits if len(digits) == 11 else None


def build_address(row: dict[str, str]) -> str:
    parts = [
        row.get("tipo_via", "").strip(),
        row.get("nombre_via", "").strip(),
        row.get("numero", "").strip(),
        row.get("interior", "").strip(),
        row.get("lote", "").strip(),
        row.get("departamento", "").strip(),
        row.get("manzana", "").strip(),
        row.get("kilometro", "").strip(),
    ]
    cleaned = [p for p in parts if p and p not in ("-", "S/N", "S/N ", "")]
    return " ".join(cleaned) if cleaned else ""


def iter_sunat_rows(zipped_txt_path: Path) -> Iterator[dict[str, str]]:
    with zipfile.ZipFile(zipped_txt_path) as archive:
        txt_name = None
        for name in archive.namelist():
            lowered = name.lower()
            if lowered.endswith(".txt") and not lowered.startswith("__MACOSX"):
                txt_name = name
                break
        if not txt_name:
            raise ValueError(f"No TXT found in ZIP: {archive.namelist()}")
        with archive.open(txt_name) as raw_file:
            for raw_line in raw_file:
                line = raw_line.decode("iso-8859-1", errors="replace").rstrip("\r\n")
                if not line.strip():
                    continue
                parts = [part.strip() for part in line.split("|")]
                if len(parts) < len(SUNAT_COLUMNS):
                    continue
                yield {col: parts[i] if i < len(parts) else "" for i, col in enumerate(SUNAT_COLUMNS)}


def download_padron(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / "padron_reducido_ruc.zip"
    print(f"Downloading SUNAT Padrón from {SUNAT_ZIP_URL}...", flush=True)
    req = urllib.request.Request(SUNAT_ZIP_URL, headers={"User-Agent": f"AgentePerry-SUNAT/{SCRIPT_VERSION}"})
    with urllib.request.urlopen(req, timeout=300) as response:
        zip_path.write_bytes(response.read())
    print(f"  Downloaded to {zip_path} ({zip_path.stat().st_size / 1024 / 1024:.1f} MB)", flush=True)
    return zip_path


def load_ocds_rucs(processes_csv: Path) -> set[str]:
    rucs: set[str] = set()
    if not processes_csv.exists():
        return rucs
    with processes_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ruc = normalize_ruc(row.get("entity_ruc", ""))
            if ruc:
                rucs.add(ruc)
    return rucs


def write_suppliers_enriched(
    zip_path: Path,
    output_dir: Path,
    rucs_to_keep: set[str] | None = None,
    batch_size: int = 100_000,
    limit: int | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "sunat_enriched.csv"
    checksum_path = output_dir / "sunat_checksum.txt"

    checksum = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    checksum_path.write_text(checksum)

    FIELDNAMES = ["ruc", "razon_social", "estado", "condicion", "ubigeo", "domicilio_fiscal"]
    total_rows = 0
    matched_rows = 0
    active_count = 0
    baja_count = 0
    no_habido_count = 0
    seen_rucs: set[str] = set()
    write_count = 0

    output_file = output_path.open("w", encoding="utf-8", newline="")
    writer = csv.DictWriter(output_file, fieldnames=FIELDNAMES, extrasaction="ignore")
    writer.writeheader()

    for row in iter_sunat_rows(zip_path):
        total_rows += 1
        ruc = normalize_ruc(row.get("ruc"))
        if not ruc:
            continue

        if rucs_to_keep is not None and ruc not in rucs_to_keep:
            if total_rows % 500_000 == 0:
                print(f"  Skipped {total_rows:,} rows (looking for {len(rucs_to_keep):,} RUCs)...", flush=True)
            continue

        if ruc in seen_rucs:
            continue
        seen_rucs.add(ruc)

        estado = row.get("estado", "").strip().upper()
        condicion = row.get("condicion", "").strip().upper()

        enriched = {
            "ruc": ruc,
            "razon_social": row.get("razon_social", "").strip() or "",
            "estado": estado,
            "condicion": condicion,
            "ubigeo": row.get("ubigeo", "").strip() or "",
            "domicilio_fiscal": build_address(row),
        }
        writer.writerow(enriched)
        matched_rows += 1
        write_count += 1

        if estado == "ACTIVO":
            active_count += 1
        elif estado == "BAJA":
            baja_count += 1
        if condicion == "NO HABIDO":
            no_habido_count += 1

        if total_rows % 1_000_000 == 0:
            print(f"  Processed {total_rows:,} rows, matched {matched_rows:,}...", flush=True)

        if limit and write_count >= limit:
            break

    output_file.close()

    return {
        "total_rows_in_padron": total_rows,
        "matched_rows": matched_rows,
        "active_count": active_count,
        "baja_count": baja_count,
        "no_habido_count": no_habido_count,
        "output_csv": str(output_path),
        "checksum_sha256": checksum,
        "limit_applied": limit,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Download and parse SUNAT Padrón Reducido.")
    parser.add_argument("--output-dir", type=Path, default=Path("data/sunat"))
    parser.add_argument("--processes-csv", type=Path, default=Path("data/scraped/seace_salud/processes.csv"),
                        help="OCDS processes.csv to extract entity_rucs for filtering")
    parser.add_argument("--limit", type=int, default=None, help="Limit matched rows (for testing)")
    parser.add_argument("--download-only", action="store_true", help="Only download, don't parse")
    args = parser.parse_args()

    zip_path = download_padron(args.output_dir)

    if args.download_only:
        print(f"Download complete: {zip_path}")
        return 0

    rucs_to_keep = None
    if args.processes_csv.exists():
        rucs_to_keep = load_ocds_rucs(args.processes_csv)
        print(f"Filtering to {len(rucs_to_keep):,} entity RUCS from OCDS...", flush=True)
    else:
        print("No processes.csv found — enriching ALL RUCs in padron.", flush=True)

    result = write_suppliers_enriched(
        zip_path=zip_path,
        output_dir=args.output_dir,
        rucs_to_keep=rucs_to_keep,
        limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())