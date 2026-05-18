"""Build searchable document chunks from generic source records."""

from __future__ import annotations

import json
from typing import Any, cast

from agenteperry.db.client import DbClient

db = DbClient()


def build_contract_chunk_text(row: dict[str, Any]) -> str:
    """Create a concise narrative chunk for one procurement source record."""
    parsed_obj = row.get("parsed_data")
    parsed_data = cast(dict[str, Any], parsed_obj) if isinstance(parsed_obj, dict) else {}
    procedure_type = parsed_data.get("procedure_type")
    tender_id = parsed_data.get("tender_id")
    award_id = parsed_data.get("award_id")
    lines = [
        f"Contrato publico OCDS: {row.get('external_id') or 'sin external_id'}.",
        f"Entidad contratante: {row.get('entity_name') or 'Entidad no identificada'}.",
        f"Proveedor adjudicado: {row.get('supplier_name') or 'Proveedor no identificado'}.",
    ]

    if row.get("monto") is not None:
        lines.append(f"Monto adjudicado: PEN {row['monto']}.")
    if row.get("fecha"):
        lines.append(f"Fecha registrada: {row['fecha']}.")
    if procedure_type:
        lines.append(f"Tipo de procedimiento: {procedure_type}.")
    if tender_id:
        lines.append(f"Tender ID: {tender_id}.")
    if award_id:
        lines.append(f"Award ID: {award_id}.")
    if row.get("evidence_quote"):
        lines.append(f"Evidencia normalizada: {row['evidence_quote']}")

    return "\n".join(lines)


def upsert_contract_chunks(
    source_code: str = "ocds_peru",
    limit: int | None = None,
    batch_size: int = 500,
) -> int:
    """Upsert narrative chunks into document_chunks for source_records contracts."""
    params: list[Any] = [source_code]
    limit_sql = ""
    if limit is not None:
        params.append(limit)
        limit_sql = "LIMIT %s"

    rows = db.execute(
        f"""
        SELECT
          sr.id::text,
          sr.external_id,
          sr.entity_name,
          sr.entity_ruc,
          sr.supplier_name,
          sr.supplier_ruc,
          sr.monto::float8 AS monto,
          sr.fecha::text AS fecha,
          sr.period_year,
          sr.parsed_data,
          sr.evidence_quote,
          sr.checksum,
          sr.raw_path,
          sr.source_url,
          sc.source_code
        FROM source_records sr
        JOIN source_catalog sc ON sc.id = sr.source_id
        WHERE sc.source_code = %s
          AND sr.external_id IS NOT NULL
        ORDER BY sr.fecha DESC NULLS LAST, sr.monto DESC NULLS LAST
        {limit_sql}
        """,
        tuple(params),
    )

    if not rows:
        return 0

    chunk_rows: list[dict[str, Any]] = []
    for row in rows:
        metadata = {
            "source_code": row.get("source_code"),
            "source_record_id": row.get("id"),
            "external_id": row.get("external_id"),
            "entity_name": row.get("entity_name"),
            "entity_ruc": row.get("entity_ruc"),
            "supplier_name": row.get("supplier_name"),
            "supplier_ruc": row.get("supplier_ruc"),
            "monto": row.get("monto"),
            "fecha": row.get("fecha"),
            "period_year": row.get("period_year"),
            "checksum": row.get("checksum"),
            "raw_path": row.get("raw_path"),
            "source_url": row.get("source_url"),
        }
        chunk_rows.append({
            "source_type": "contrato",
            "source_id": row["id"],
            "external_ref": row["external_id"],
            "chunk_index": 0,
            "text_content": build_contract_chunk_text(row),
            "metadata": json.dumps(metadata),
            "tags": ["ocds", "contrato", str(row.get("period_year") or "sin_anio")],
        })

    query = """
        INSERT INTO document_chunks (
          source_type, source_id, external_ref, chunk_index, text_content, metadata, tags
        ) VALUES (
          %(source_type)s, %(source_id)s, %(external_ref)s, %(chunk_index)s,
          %(text_content)s, %(metadata)s, %(tags)s
        )
        ON CONFLICT (source_type, external_ref, chunk_index) DO UPDATE SET
          source_id = EXCLUDED.source_id,
          text_content = EXCLUDED.text_content,
          metadata = EXCLUDED.metadata,
          tags = EXCLUDED.tags
    """

    total = 0
    for start in range(0, len(chunk_rows), batch_size):
        batch = chunk_rows[start : start + batch_size]
        db.execute_batch(query, batch)
        total += len(batch)
    return total
