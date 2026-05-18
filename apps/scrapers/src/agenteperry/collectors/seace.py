"""SEACE/OECE open-data collector helpers."""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Any

from agenteperry.collectors.base import BulkDownloadCollector, CollectionResult


class SeaceOeceCollector(BulkDownloadCollector):
    """Parse SEACE/OECE CSV exports into normalized contract records."""

    def collect(
        self,
        download_dir: Path | None = None,
        input_path: Path | None = None,
        download_url: str | None = None,
        limit: int | None = None,
        **_: Any,
    ) -> list[CollectionResult]:
        if input_path is None:
            if not download_url or download_dir is None:
                raise ValueError("SEACE collector needs input_path or download_url + download_dir")
            input_path = self.download(download_url, download_dir)

        checksum = self.calculate_checksum(input_path.read_bytes())
        rows = iter_seace_csv_rows(input_path)
        results: list[CollectionResult] = []
        for row in rows:
            results.append(seace_row_to_result(row, input_path, checksum))
            if limit is not None and len(results) >= limit:
                return results
        return results


def iter_seace_csv_rows(path: Path) -> list[dict[str, str]]:
    """Read SEACE/OECE CSV exports with UTF-8 or Latin-1 fallback."""
    text = _read_text(path)
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;|	")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    return [{str(key).strip(): (value or "").strip() for key, value in row.items()} for row in reader]


def seace_row_to_result(row: dict[str, str], raw_path: Path | None = None, checksum: str | None = None) -> CollectionResult:
    external_id = _pick(row, "codigo_proceso", "codigo", "id_proceso", "n_proceso", "proceso")
    entity_name = _pick(row, "entidad", "nombre_entidad", "comprador", "entidad_contratante")
    supplier_name = _pick(row, "proveedor", "contratista", "adjudicatario", "ganador")
    entity_ruc = _normalize_ruc(_pick(row, "ruc_entidad", "entidad_ruc", "ruccomprador"))
    supplier_ruc = _normalize_ruc(_pick(row, "ruc_proveedor", "proveedor_ruc", "ruccontratista", "ruc"))
    amount = _parse_amount(_pick(row, "monto", "monto_adjudicado", "valor_adjudicado", "importe"))
    fecha = _parse_date(_pick(row, "fecha", "fecha_adjudicacion", "fecha_buena_pro", "fecha_publicacion"))
    region = _pick(row, "region", "departamento")

    return CollectionResult(
        source_code="seace_oece",
        external_id=external_id,
        record_type="contract",
        raw_data=row,
        parsed_data={
            "codigo_proceso": external_id,
            "modalidad": _pick(row, "modalidad", "tipo_proceso", "procedimiento"),
            "objeto": _pick(row, "objeto", "descripcion", "nomenclatura"),
        },
        raw_path=raw_path,
        checksum=checksum,
        content_type="text/csv",
        period_year=fecha.year if fecha else None,
        region=region,
        entity_name=entity_name,
        entity_ruc=entity_ruc,
        supplier_name=supplier_name,
        supplier_ruc=supplier_ruc,
        monto=amount,
        fecha=fecha,
        evidence_quote=_build_evidence_quote(entity_name, supplier_name, external_id, amount),
    )


def _read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _pick(row: dict[str, str], *names: str) -> str | None:
    normalized = {_normalize_key(key): value for key, value in row.items()}
    for name in names:
        value = normalized.get(_normalize_key(name))
        if value:
            return value.strip()
    return None


def _normalize_key(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _normalize_ruc(value: str | None) -> str | None:
    digits = "".join(ch for ch in value or "" if ch.isdigit())
    return digits if len(digits) == 11 else None


def _parse_amount(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = value.replace("S/", "").replace(" ", "").strip()
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(",", "")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    cleaned = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(cleaned[:10], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _build_evidence_quote(entity: str | None, supplier: str | None, external_id: str | None, amount: float | None) -> str:
    amount_text = f" por {amount:.2f}" if amount is not None else ""
    return f"SEACE registra el proceso {external_id or 'sin codigo'} entre {entity or 'entidad no identificada'} y {supplier or 'proveedor no identificado'}{amount_text}."
