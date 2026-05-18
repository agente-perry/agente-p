#!/usr/bin/env python3
"""Download and filter OCDS Peru data for salud and ambiente sectors."""

from __future__ import annotations

import csv
import gzip
import json
import re
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "1.0.0"
OCDS_URL_TEMPLATE = "https://data.open-contracting.org/es/publication/135/download?name={year}.jsonl.gz"
HEALTH_KEYWORDS = [
    "salud",
    "essalud",
    "minsa",
    "hospital",
    "instituto nacional de salud",
    "direccion general de salud",
    "direccion regional de salud",
    "red de salud",
    "microred",
    "oncosalud",
    "sanidad",
    "epidemiologia",
    "vacunas",
    "insumos medicos",
    "laboratorio",
    "diagnostico",
    "tratamiento",
    "clinica",
    "centro de salud",
    "puesto de salud",
    "samú",
    "samu",
    "emergencia",
    "atencion primaria",
]
AMBIENTE_KEYWORDS = [
    "ambiente",
    "ministerio del ambiente",
    "servicio nacional de asuntos",
    "organismo de evaluacion",
    "evaluacion ambiental",
    "recursos naturales",
    "biodiversidad",
    " Areas Protegidas",
    "conservacion",
    "cambio climatico",
    "descontaminacion",
    "residuos solidos",
    "agua",
    "manejo de residuos",
    "OEFA",
    "SENAPE",
    "autoridad ambiental",
]


PROCESS_FIELDS = [
    "process_id",
    "ocid",
    "seace_code",
    "sector",
    "entity_name",
    "entity_ruc",
    "procedure_type",
    "object_description",
    "status",
    "amount_estimated",
    "currency",
    "publication_date",
    "award_date",
    "source_url",
    "scraped_at",
]

DOCUMENT_FIELDS = [
    "document_id",
    "process_id",
    "document_type",
    "file_name",
    "file_path",
    "file_url",
    "source_url",
    "mime_type",
    "file_size_bytes",
    "sha256",
    "pages_total",
    "pages_with_text",
    "pages_needing_ocr",
    "text_coverage_ratio",
    "ocr_class",
    "ocr_required",
    "ocr_status",
    "downloaded_at",
    "parse_status",
    "error_message",
]

AWARD_FIELDS = [
    "award_id",
    "process_id",
    "supplier_name",
    "supplier_ruc",
    "award_amount",
    "award_currency",
    "award_date",
    "award_document_id",
    "award_source_quote",
    "award_source_page",
    "confidence",
]

DOCUMENT_TYPE_PATTERNS = {
    "tdr": [r"terminos?\s+de\s+referencia", r"\btdr\b", r"\bTDR\b"],
    "bases": [r"bases?\s+administrativas?", r"bases\s+integradas?", r"bases"],
    "bases_integradas": [r"bases\s+integradas?"],
    "pliego_absolucion": [r"pliego\s+de\s+absolu", r"absolu\s+consul", r"absolucion"],
    "consultas_observaciones": [r"consulta", r"observaciones", r"consultas?\s+y?\s+obs"],
    "acta": [r"acta\s+de", r"acta\s+de\s+buena\s+pro", r"\bacta\b"],
    "buena_pro": [r"buena\s+pro", r"resultado\s+buena\s+pro"],
    "contrato": [r"contrato"],
    "documento_ganador": [r"documento\s+ganador", r"propuesta\s+ganadora"],
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def detect_sector(entity_name: str, tender_title: str = "") -> str | None:
    combined = normalize_text(f"{entity_name} {tender_title}")
    health_score = sum(1 for kw in HEALTH_KEYWORDS if kw.lower() in combined)
    ambiente_score = sum(1 for kw in AMBIENTE_KEYWORDS if kw.lower() in combined)
    if health_score >= 1 and ambiente_score == 0:
        return "salud"
    if ambiente_score >= 1 and health_score == 0:
        return "ambiente"
    if health_score >= 1 and ambiente_score >= 1:
        return "salud"
    return None


def classify_document_type(title: str) -> str:
    text = normalize_text(title)
    for doc_type, patterns in DOCUMENT_TYPE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.I):
                return doc_type
    return "otros"


def normalize_ruc(value: str | None) -> str | None:
    digits = "".join(ch for ch in (value or "").strip() if ch.isdigit())
    return digits if len(digits) == 11 else None


def parse_iso_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return value[:10] if len(value) >= 10 else None


def extract_party_ruc(party: dict[str, Any]) -> str | None:
    identifier = party.get("identifier") or {}
    scheme = str(identifier.get("scheme") or "")
    ruc_id = str(identifier.get("id") or "")
    if scheme == "PE-RUC" or "RUC" in scheme.upper():
        return normalize_ruc(ruc_id)
    for additional in party.get("additionalIdentifiers") or []:
        if str(additional.get("scheme") or "").upper().find("RUC") >= 0:
            return normalize_ruc(str(additional.get("id") or ""))
    return None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def parse_ocds_release(release: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    ocid = str(release.get("ocid") or release.get("id") or "")
    tender = _as_dict(release.get("tender"))
    buyer = _as_dict(release.get("buyer"))
    awards = _as_list(release.get("awards"))
    contracts = _as_list(release.get("contracts"))
    parties = _as_list(release.get("parties"))

    entity_name = str(buyer.get("name") or release.get("buyer", {}).get("name") or "").strip()
    tender_id = str(tender.get("id") or "").strip()
    tender_title = str(tender.get("title") or "").strip()
    procurement_method = str(tender.get("procurementMethodDetails") or tender.get("procurementMethod") or "").strip()
    status = str(tender.get("status") or release.get("status") or "").strip()
    object_description = str(tender.get("description") or "").strip()
    source_url = str(release.get("url") or "").strip()

    tender_value = _as_dict(tender.get("value") or {})
    amount_str = tender_value.get("amount")
    currency = tender_value.get("currency", "PEN")
    try:
        amount_estimated = float(amount_str) if amount_str else ""
    except (ValueError, TypeError):
        amount_estimated = ""

    publication_date = parse_iso_date(tender.get("datePublished") or release.get("date"))
    award_date = None

    entity_ruc = None
    for party in parties:
        roles = _as_list(party.get("roles"))
        if "buyer" in roles:
            entity_ruc = extract_party_ruc(party)
            if entity_ruc:
                break

    sector = detect_sector(entity_name, tender_title)
    if not sector:
        return []

    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    tender_documents = _as_list(tender.get("documents") or [])

    process_record: dict[str, Any] = {
        "process_id": ocid,
        "ocid": ocid,
        "seace_code": tender_id,
        "sector": sector,
        "entity_name": entity_name,
        "entity_ruc": entity_ruc or "",
        "procedure_type": procurement_method,
        "object_description": object_description,
        "status": status,
        "amount_estimated": amount_estimated,
        "currency": currency,
        "publication_date": publication_date or "",
        "award_date": "",
        "source_url": source_url,
        "scraped_at": now,
    }

    documents_for_process: list[dict[str, Any]] = []
    for idx, doc in enumerate(tender_documents):
        doc_url = str(doc.get("url") or "").strip()
        if not doc_url:
            continue
        doc_title = str(doc.get("title") or f"documento_{idx}").strip()
        doc_format = str(doc.get("format") or "application/pdf").strip()
        doc_id = f"{ocid}::{idx:04d}"
        documents_for_process.append(
            {
                "document_id": doc_id,
                "process_id": ocid,
                "document_type": classify_document_type(doc_title),
                "file_name": doc_title.replace("/", "_").replace("\\", "_")[:200],
                "file_path": "",
                "file_url": doc_url,
                "source_url": source_url,
                "mime_type": doc_format,
                "file_size_bytes": "",
                "sha256": "",
                "pages_total": "",
                "pages_with_text": "",
                "pages_needing_ocr": "",
                "text_coverage_ratio": "",
                "ocr_class": "",
                "ocr_required": "",
                "ocr_status": "pending",
                "downloaded_at": "",
                "parse_status": "pending",
                "error_message": "",
            }
        )

    awards_data: list[dict[str, Any]] = []
    for aw_idx, award in enumerate(awards):
        award_dict = _as_dict(award)
        award_date = parse_iso_date(award_dict.get("date"))
        if not process_record["award_date"] and award_date:
            process_record["award_date"] = award_date

        suppliers = _as_list(award_dict.get("suppliers") or [])
        for sup_idx, supplier in enumerate(suppliers):
            supplier_dict = _as_dict(supplier)
            supplier_name = str(supplier_dict.get("name") or "").strip()
            supplier_id = str(supplier_dict.get("id") or "").strip()
            supplier_ruc = normalize_ruc(supplier_id)
            if not supplier_ruc and parties:
                for party in parties:
                    roles = _as_list(party.get("roles"))
                    if "supplier" in roles:
                        supplier_ruc = extract_party_ruc(party)
                        if supplier_ruc:
                            break

            award_value = _as_dict(award_dict.get("value") or {})
            try:
                award_amount = float(award_value.get("amount") or 0)
            except (ValueError, TypeError):
                award_amount = ""

            award_id = f"{ocid}::award::{aw_idx:04d}"
            awards_data.append(
                {
                    "award_id": award_id,
                    "process_id": ocid,
                    "supplier_name": supplier_name,
                    "supplier_ruc": supplier_ruc or "",
                    "award_amount": award_amount,
                    "award_currency": award_value.get("currency", "PEN"),
                    "award_date": award_date or "",
                    "award_document_id": "",
                    "award_source_quote": "",
                    "award_source_page": "",
                    "confidence": "medium",
                }
            )
            if sup_idx == 0 and aw_idx == 0:
                process_record["award_date"] = award_date or process_record["award_date"]

    return [{"type": "process", "data": process_record, "documents": documents_for_process, "awards": awards_data}]


def iter_ocds_gz(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": f"AgentePerry-OCDS-Downloader/{SCRIPT_VERSION}"})
    with urllib.request.urlopen(req, timeout=120) as response:
        raw = response.read()
    with gzip.open(raw, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    yield json.loads(line.strip())
                except json.JSONDecodeError:
                    continue


def download_and_filter(
    years: list[int] | None = None,
    output_dir: Path | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    if years is None:
        years = [2024, 2025, 2026]
    if output_dir is None:
        output_dir = Path("data/scraped/seace_salud")
    output_dir.mkdir(parents=True, exist_ok=True)

    processes_path = output_dir / "processes.csv"
    documents_path = output_dir / "documents.csv"
    awards_path = output_dir / "awards.csv"

    processes_writer = None
    documents_writer = None
    awards_writer = None

    processes_file = None
    documents_file = None
    awards_file = None

    total_contracts = 0
    salud_contracts = 0
    ambiente_contracts = 0
    skipped_sector = 0

    for year in years:
        url = OCDS_URL_TEMPLATE.format(year=year)
        print(f"Downloading OCDS {year} from {url}...", flush=True)
        try:
            releases_count = 0
            for release in iter_ocds_gz(url):
                releases_count += 1
                parsed = parse_ocds_release(release)
                if not parsed:
                    skipped_sector += 1
                    continue

                item = parsed[0]
                sector = item["data"]["sector"]
                if sector == "salud":
                    salud_contracts += 1
                elif sector == "ambiente":
                    ambiente_contracts += 1

                if processes_writer is None:
                    processes_file = processes_path.open("w", encoding="utf-8", newline="")
                    processes_writer = csv.DictWriter(processes_file, fieldnames=PROCESS_FIELDS)
                    processes_writer.writeheader()

                    documents_file = documents_path.open("w", encoding="utf-8", newline="")
                    documents_writer = csv.DictWriter(documents_file, fieldnames=DOCUMENT_FIELDS)
                    documents_writer.writeheader()

                    awards_file = awards_path.open("w", encoding="utf-8", newline="")
                    awards_writer = csv.DictWriter(awards_file, fieldnames=AWARD_FIELDS)
                    awards_writer.writeheader()

                processes_writer.writerow(item["data"])
                for doc in item["documents"]:
                    documents_writer.writerow(doc)
                for award in item["awards"]:
                    awards_writer.writerow(award)

                total_contracts += 1

                if limit and total_contracts >= limit:
                    processes_file.close()
                    documents_file.close()
                    awards_file.close()
                    return _build_summary(output_dir, total_contracts, salud_contracts, ambiente_contracts, skipped_sector, year)

                if total_contracts % 500 == 0:
                    print(f"  {total_contracts:,} contracts processed ({salud_contracts:,} salud, {ambiente_contracts:,} ambiente)", flush=True)

            print(f"  Year {year}: {releases_count:,} releases read", flush=True)

        except Exception as exc:
            print(f"  ERROR downloading year {year}: {exc}", flush=True)
            continue

    if processes_file:
        processes_file.close()
    if documents_file:
        documents_file.close()
    if awards_file:
        awards_file.close()

    return _build_summary(output_dir, total_contracts, salud_contracts, ambiente_contracts, skipped_sector, year)


def _build_summary(output_dir: Path, total: int, salud: int, ambiente: int, skipped: int, last_year: int) -> dict[str, Any]:
    return {
        "total_contracts": total,
        "salud_contracts": salud,
        "ambiente_contracts": ambiente,
        "skipped_other_sector": skipped,
        "output_dir": str(output_dir),
        "processes_csv": str(output_dir / "processes.csv"),
        "documents_csv": str(output_dir / "documents.csv"),
        "awards_csv": str(output_dir / "awards.csv"),
        "last_year_processed": last_year,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Download and filter OCDS Peru for salud and ambiente.")
    parser.add_argument("--years", type=int, nargs="+", default=[2024, 2025, 2026], help="Years to download")
    parser.add_argument("--output-dir", type=Path, default=Path("data/scraped/seace_salud"))
    parser.add_argument("--limit", type=int, default=None, help="Limit contracts (for testing)")
    args = parser.parse_args()

    result = download_and_filter(
        years=args.years,
        output_dir=args.output_dir,
        limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())