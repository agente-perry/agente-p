"""TDR Discovery script — filter OCDS contracts by priority sectors.

Usage:
    export DATABASE_URL=postgresql://...
    cd apps/scrapers
    uv run python src/agenteperry/discovery/tdr_discovery.py

Output:
    data/scraped/filtered/salud_2024_2025.jsonl
    data/scraped/filtered/ambiente_2024_2025.jsonl
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, cast

import structlog

from agenteperry.db.client import DbClient

logger = structlog.get_logger()

base_dir = Path(__file__).resolve().parents[5]  # repo root
FILTERED_DIR = base_dir / "data" / "scraped" / "filtered"
TDR_RECON_DIR = base_dir / "data" / "scraped" / "tdr_recon"

FILTERED_DIR.mkdir(parents=True, exist_ok=True)
TDR_RECON_DIR.mkdir(parents=True, exist_ok=True)

SALUD_ENTITIES = [
    "minsa",
    "ministra de salud",
    "ministerio de salud",
    "diresa",
    "red de salud",
    "hospital",
    "centro de salud",
    "cenares",
    "instituto nacional de salud",
    "essalud",
    "seguro social de salud",
    "seguro social de  salud",
]

AMBIENTE_ENTITIES = [
    "minam",
    "ministerio del ambiente",
    "oefa",
    "autoridad nacional del agua",
    "sernanp",
    "senace",
    "ingemmet",
    "autoridad regional ambiental",
    "gerencia regional ambiental",
    "autoridad ambiental",
]


def _entity_clause(keywords: list[str]) -> str:
    return " or ".join(f"entity_name ilike '%%{kw}%%'" for kw in keywords)


def build_contract_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize a DB row into a flat contract dict for JSONL export."""
    raw = cast(dict[str, Any], row.get("raw_data") or {})
    tender = cast(dict[str, Any], raw.get("tender") or {})
    contracts = cast(list[Any], raw.get("contracts") or [])
    awards = cast(list[Any], raw.get("awards") or [])

    # Supplier from first award
    supplier_name: str | None = None
    supplier_ruc: str | None = None
    if awards and awards[0].get("suppliers"):
        sup = cast(dict[str, Any], awards[0]["suppliers"][0])
        supplier_name = cast(str | None, sup.get("name"))
        supplier_ruc = cast(str, sup.get("id", "")).replace("PE-RUC-", "")

    contract_doc: dict[str, Any] | None = contracts[0] if contracts else None

    fecha_val = row.get("fecha")
    return {
        "ocid": raw.get("ocid") or row.get("external_id"),
        "external_id": row.get("external_id"),
        "entity": row.get("entity_name"),
        "entity_ruc": row.get("entity_ruc"),
        "objeto": tender.get("title") or tender.get("description"),
        "monto": float(row["monto"]) if row.get("monto") else None,
        "fecha": fecha_val.isoformat() if fecha_val else None,
        "modalidad": tender.get("procurementMethodDetails"),
        "proveedor_nombre": supplier_name or row.get("supplier_name"),
        "proveedor_ruc": supplier_ruc or row.get("supplier_ruc"),
        "source_url": row.get("source_url") or (contract_doc.get("url") if contract_doc else None),
        "parsed_data": dict(row.get("parsed_data") or {}),
    }


def fetch_contracts(
    db: DbClient,
    keywords: list[str],
    since: date = date(2024, 1, 1),
) -> list[dict[str, Any]]:
    clause = _entity_clause(keywords)
    query = f"""
        select
            external_id,
            entity_name,
            entity_ruc,
            supplier_name,
            supplier_ruc,
            monto,
            fecha,
            parsed_data,
            raw_data,
            source_url
        from source_records
        where record_type = 'contract'
          and fecha >= %s
          and ({clause})
        order by monto desc nulls last
    """
    rows = db.execute(query, (since.isoformat(),))
    return [build_contract_row(dict(r)) for r in rows]


def write_jsonl(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")


def summarize(
    records: list[dict[str, Any]],
    sector_label: str,
) -> dict[str, Any]:
    total = len(records)
    total_monto = sum(r["monto"] or 0 for r in records)

    by_entity = Counter[str]()
    monto_by_entity: dict[str, float] = {}
    by_supplier = Counter[str]()
    monto_by_supplier: dict[str, float] = {}

    for r in records:
        ent = r.get("entity") or "Sin entidad"
        by_entity[ent] += 1
        monto_by_entity[ent] = monto_by_entity.get(ent, 0) + (r["monto"] or 0)

        sup = r.get("proveedor_nombre") or "Sin proveedor"
        by_supplier[sup] += 1
        monto_by_supplier[sup] = monto_by_supplier.get(sup, 0) + (r["monto"] or 0)

    top_entities_count = by_entity.most_common(20)
    top_entities_monto = sorted(monto_by_entity.items(), key=lambda x: x[1], reverse=True)[:20]
    top_suppliers_count = by_supplier.most_common(20)
    top_suppliers_monto = sorted(monto_by_supplier.items(), key=lambda x: x[1], reverse=True)[:20]

    return {
        "sector": sector_label,
        "total_records": total,
        "total_monto": round(total_monto, 2),
        "top_entities_count": top_entities_count,
        "top_entities_monto": [(e, round(m, 2)) for e, m in top_entities_monto],
        "top_suppliers_count": top_suppliers_count,
        "top_suppliers_monto": [(s, round(m, 2)) for s, m in top_suppliers_monto],
    }


def pick_sample(records: list[dict[str, Any]], n: int = 10) -> list[dict[str, Any]]:
    """Pick diverse high-value samples with direct-award preference."""
    scored: list[tuple[float, dict[str, Any]]] = []
    for r in records:
        score = (r.get("monto") or 0) / 1e6
        modalidad = (r.get("modalidad") or "").lower()
        if "directa" in modalidad or "adjudicación" in modalidad or "menor cuantía" in modalidad:
            score += 50
        if r.get("objeto") and len(str(r["objeto"])) > 30:
            score += 10
        if r.get("proveedor_ruc") and str(r["proveedor_ruc"]).isdigit():
            score += 5
        scored.append((score, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    # Deduplicate by ocid to avoid the same tender repeated
    seen_ocids: set[str] = set()
    sample: list[dict[str, Any]] = []
    for _, r in scored:
        ocid = cast(str, r.get("ocid") or r.get("external_id"))
        if ocid in seen_ocids:
            continue
        seen_ocids.add(ocid)
        sample.append(r)
        if len(sample) >= n:
            break
    return sample


def main() -> None:
    db = DbClient()

    # 1. Salud
    logger.info("Fetching Salud contracts...")
    salud_records = fetch_contracts(db, SALUD_ENTITIES)
    salud_path = FILTERED_DIR / "salud_2024_2025.jsonl"
    write_jsonl(salud_records, salud_path)
    logger.info("Saved %d records to %s", len(salud_records), salud_path)

    # 2. Ambiente/Minería
    logger.info("Fetching Ambiente/Minería contracts...")
    ambiente_records = fetch_contracts(db, AMBIENTE_ENTITIES)
    ambiente_path = FILTERED_DIR / "ambiente_2024_2025.jsonl"
    write_jsonl(ambiente_records, ambiente_path)
    logger.info("Saved %d records to %s", len(ambiente_records), ambiente_path)

    # 3. Summaries
    salud_summary = summarize(salud_records, "salud")
    ambiente_summary = summarize(ambiente_records, "ambiente_mineria")

    summary_path = FILTERED_DIR / "summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump({"salud": salud_summary, "ambiente": ambiente_summary}, f, ensure_ascii=False, indent=2, default=str)
    logger.info("Summary saved to %s", summary_path)

    # 4. Sample of 20 for recon
    salud_sample = pick_sample(salud_records, n=10)
    ambiente_sample = pick_sample(ambiente_records, n=10)

    recon_path = TDR_RECON_DIR / "recon_20_processes.csv"
    # Write CSV header + rows
    import csv

    fieldnames = [
        "ocid", "sector", "entidad", "objeto", "monto", "fecha",
        "proveedor_nombre", "proveedor_ruc", "source_url",
        "seace_url_candidate", "tdr_status", "tdr_url", "tdr_path",
        "access_method", "notes",
    ]
    with recon_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in salud_sample:
            writer.writerow({
                "ocid": r.get("ocid"),
                "sector": "salud",
                "entidad": r.get("entity"),
                "objeto": r.get("objeto"),
                "monto": r.get("monto"),
                "fecha": r.get("fecha"),
                "proveedor_nombre": r.get("proveedor_nombre"),
                "proveedor_ruc": r.get("proveedor_ruc"),
                "source_url": r.get("source_url"),
                "seace_url_candidate": _seace_url(r),
                "tdr_status": "pending",
                "tdr_url": "",
                "tdr_path": "",
                "access_method": "",
                "notes": f"Modalidad: {r.get('modalidad') or 'N/A'}",
            })
        for r in ambiente_sample:
            writer.writerow({
                "ocid": r.get("ocid"),
                "sector": "ambiente_mineria",
                "entidad": r.get("entity"),
                "objeto": r.get("objeto"),
                "monto": r.get("monto"),
                "fecha": r.get("fecha"),
                "proveedor_nombre": r.get("proveedor_nombre"),
                "proveedor_ruc": r.get("proveedor_ruc"),
                "source_url": r.get("source_url"),
                "seace_url_candidate": _seace_url(r),
                "tdr_status": "pending",
                "tdr_url": "",
                "tdr_path": "",
                "access_method": "",
                "notes": f"Modalidad: {r.get('modalidad') or 'N/A'}",
            })

    logger.info("Recon CSV saved to %s", recon_path)

    # 5. Update recon CSV with real TDR availability
    logger.info("Updating recon CSV with TDR availability from DB...")
    update_recon_csv(db, recon_path)

    # Print top-level stats
    logger.info("SALUD:      %d contratos", len(salud_records))
    logger.info("  Top entity (count):  %s", salud_summary['top_entities_count'][0] if salud_summary['top_entities_count'] else 'N/A')
    logger.info("  Top entity (monto):  %s", salud_summary['top_entities_monto'][0] if salud_summary['top_entities_monto'] else 'N/A')
    logger.info("AMBIENTE:   %d contratos", len(ambiente_records))
    logger.info("  Top entity (count):  %s", ambiente_summary['top_entities_count'][0] if ambiente_summary['top_entities_count'] else 'N/A')
    logger.info("  Top entity (monto):  %s", ambiente_summary['top_entities_monto'][0] if ambiente_summary['top_entities_monto'] else 'N/A')


def _seace_url(record: dict[str, Any]) -> str:
    """Build candidate SEACE URL from ocid/tender info."""
    ocid = record.get("ocid") or ""
    # ocid pattern: ocds-dgv273-seacev3-2025-200208-29
    # SEACE URL pattern is not deterministic from ocid alone
    # Best effort: base URL
    if "seace" in ocid.lower():
        return "https://www.seace.gob.pe/"
    return ""


def _extract_doc_urls(raw_data: dict[str, Any]) -> list[dict[str, str]]:
    """Extract document URLs from OCDS raw_data."""
    urls: list[dict[str, str]] = []
    tender = cast(dict[str, Any], raw_data.get("tender") or {})
    contracts = cast(list[Any], raw_data.get("contracts") or [])
    awards = cast(list[Any], raw_data.get("awards") or [])

    for d in cast(list[Any], tender.get("documents", [])):
        if d.get("url"):
            urls.append({
                "type": "tender",
                "title": cast(str, d.get("title", "")),
                "url": cast(str, d["url"]),
            })

    for a in awards:
        for d in cast(list[Any], cast(dict[str, Any], a).get("documents", [])):
            if d.get("url"):
                urls.append({
                    "type": "award",
                    "title": cast(str, d.get("title", "")),
                    "url": cast(str, d["url"]),
                })

    for c in contracts:
        for d in cast(list[Any], cast(dict[str, Any], c).get("documents", [])):
            if d.get("url"):
                urls.append({
                    "type": "contract",
                    "title": cast(str, d.get("title", "")),
                    "url": cast(str, d["url"]),
                })

    return urls


def update_recon_csv(db: DbClient, recon_path: Path) -> None:
    """Update recon CSV with real TDR availability data from DB."""
    import csv

    # Read existing CSV
    rows: list[dict[str, str]] = []
    with recon_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))

    for row in rows:
        ocid = row.get("ocid", "")
        if not ocid:
            continue

        # Find contract in DB by ocid
        db_rows = db.execute(
            """
            select raw_data
            from source_records
            where record_type = 'contract'
              and raw_data->>'ocid' = %s
            limit 1
            """,
            (ocid,),
        )
        if not db_rows:
            row["tdr_status"] = "not_found"
            row["notes"] = "Process not found in OCDS data"
            continue

        raw = dict(db_rows[0]["raw_data"])
        docs = _extract_doc_urls(raw)

        if not docs:
            row["tdr_status"] = "no_docs"
            row["notes"] = "No tender/award/contract documents in OCDS record"
            continue

        # Check for specific document types
        bases = [d for d in docs if "base" in d["title"].lower() or "tdr" in d["title"].lower()]
        pliego = [d for d in docs if "pliego" in d["title"].lower()]

        if bases:
            row["tdr_status"] = "available"
            row["tdr_url"] = bases[0]["url"]
            row["access_method"] = "direct_url_seace"
            row["notes"] = f"Bases found: {len(bases)}. Pliegos: {len(pliego)}. Total docs: {len(docs)}"
        elif pliego:
            row["tdr_status"] = "available"
            row["tdr_url"] = pliego[0]["url"]
            row["access_method"] = "direct_url_seace"
            row["notes"] = f"Pliego found. Total docs: {len(docs)}"
        else:
            row["tdr_status"] = "docs_other"
            row["tdr_url"] = docs[0]["url"]
            row["access_method"] = "direct_url_seace"
            row["notes"] = f"Other docs: {', '.join(d['title'] for d in docs[:3])}"

    # Write updated CSV
    fieldnames = [
        "ocid", "sector", "entidad", "objeto", "monto", "fecha",
        "proveedor_nombre", "proveedor_ruc", "source_url",
        "seace_url_candidate", "tdr_status", "tdr_url", "tdr_path",
        "access_method", "notes",
    ]
    with recon_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    logger.info("Updated recon CSV with TDR availability for %d processes", len(rows))


if __name__ == "__main__":
    main()
