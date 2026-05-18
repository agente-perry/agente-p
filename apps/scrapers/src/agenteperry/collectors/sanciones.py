"""OECE/SEACE Sanctions collector — proveedores inhabilitados.

Fuente: https://www.datosabiertos.gob.pe/dataset/proveedores-sancionados-con-inhabilitacion-vigente

Método: bulk CSV download desde portal de datos abiertos del gobierno peruano.
No requiere Playwright ni CAPTCHA. El archivo se actualiza semanalmente.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any

from agenteperry.collectors.base import BulkDownloadCollector, CollectionResult

SANCIONES_URL = (
    "https://www.datosabiertos.gob.pe/dataset/"
    "proveedores-sancionados-con-inhabilitacion-vigente-organismo-supervisor-de-las"
    "/download"
)


class SancionesCollector(BulkDownloadCollector):
    """Collect and normalize OECE sanctions records."""

    def collect(
        self,
        download_dir: Path | None = None,
        input_path: Path | None = None,
        download_url: str | None = None,
        limit: int | None = None,
        **_: Any,
    ) -> list[CollectionResult]:
        if input_path is None:
            if download_dir is None:
                raise ValueError("Sanciones collector needs input_path or download_dir")
            resolved_url = download_url or SANCIONES_URL
            input_path = self.download(resolved_url, download_dir, filename="sanciones_oece.csv")

        checksum = self.calculate_checksum(input_path.read_bytes())
        results: list[CollectionResult] = []
        for row in iter_sanciones_rows(input_path):
            results.append(sancion_row_to_result(row, input_path, checksum))
            if limit is not None and len(results) >= limit:
                return results
        return results


def iter_sanciones_rows(path: Path) -> list[dict[str, str]]:
    """Parse sanciones CSV with flexible column detection."""
    text = _read_text(path)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;|\t")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    normalized: list[dict[str, str]] = []
    for row in reader:
        cleaned = {str(k).strip(): (v or "").strip() for k, v in row.items()}
        mapped = _map_columns(cleaned)
        if mapped:
            normalized.append(mapped)
    return normalized


def _map_columns(row: dict[str, str]) -> dict[str, str]:
    """Normalize column names to the expected canonical names."""
    inverse: dict[str, str] = {}
    for key, value in row.items():
        norm_key = _normalize_key(key)
        if norm_key in KNOWN_COLUMNS:
            inverse[KNOWN_COLUMNS[norm_key]] = value
        else:
            inverse[key] = value
    return {
        "ruc": inverse.get("ruc", ""),
        "razon_social": inverse.get("razon_social", ""),
        "resolucion": inverse.get("resolucion", ""),
        "tipo_sancion": inverse.get("tipo_sancion", ""),
        "fecha_inicio": inverse.get("fecha_inicio", ""),
        "fecha_fin": inverse.get("fecha_fin", ""),
        "estado": inverse.get("estado", ""),
        "infraccion": inverse.get("infraccion", ""),
        "entidad": inverse.get("entidad", ""),
    }


KNOWN_COLUMNS: dict[str, str] = {
    "ruc": "ruc",
    "numeroruc": "ruc",
    "nroruc": "ruc",
    "n_documento": "ruc",
    "razonsocial": "razon_social",
    "nombreorazonsocial": "razon_social",
    "denominacion": "razon_social",
    "resolucion": "resolucion",
    "nro_resolucion": "resolucion",
    "numero_de_resolucion": "resolucion",
    "resolucion_tcp": "resolucion",
    "tipo": "tipo_sancion",
    "tipo_sancion": "tipo_sancion",
    "tipo_inhabilitacion": "tipo_sancion",
    "sancion": "tipo_sancion",
    "fechainicio": "fecha_inicio",
    "fecha_de_inicio": "fecha_inicio",
    "fec_ini": "fecha_inicio",
    "inicio": "fecha_inicio",
    "fechafin": "fecha_fin",
    "fecha_de_fin": "fecha_fin",
    "fec_fin": "fecha_fin",
    "fin": "fecha_fin",
    "estado": "estado",
    "estado_sancion": "estado",
    "condicion": "estado",
    "infraccion": "infraccion",
    "tipo_infraccion": "infraccion",
    "detalle_infraccion": "infraccion",
    "descripcion_infraccion": "infraccion",
    "entidad": "entidad",
    "entidad_sancionadora": "entidad",
    "organismo": "entidad",
}


def sancion_row_to_result(
    row: dict[str, str],
    raw_path: Path | None = None,
    checksum: str | None = None,
) -> CollectionResult:
    ruc = _normalize_ruc(row.get("ruc"))
    razon_social = _clean(row.get("razon_social"))
    resolucion = _clean(row.get("resolucion"))
    tipo_sancion = _normalize_tipo(_clean(row.get("tipo_sancion")))
    fecha_inicio = _parse_date(row.get("fecha_inicio"))
    fecha_fin = _parse_date(row.get("fecha_fin")) if row.get("fecha_fin") else None
    estado = _normalize_estado(_clean(row.get("estado")))
    infraccion = _clean(row.get("infraccion"))
    entidad = _clean(row.get("entidad"))

    return CollectionResult(
        source_code="contraloria_sanciones",
        external_id=f"{ruc}:{resolucion}" if ruc and resolucion else ruc,
        record_type="sanction",
        raw_data=row,
        parsed_data={
            "ruc": ruc,
            "razon_social": razon_social,
            "resolucion": resolucion,
            "tipo_sancion": tipo_sancion,
            "fecha_inicio": fecha_inicio.isoformat() if fecha_inicio else None,
            "fecha_fin": fecha_fin.isoformat() if fecha_fin else None,
            "estado": estado,
            "infraccion": infraccion,
            "entidad_sancionadora": entidad,
        },
        raw_path=raw_path,
        checksum=checksum,
        content_type="text/csv",
        period_year=fecha_inicio.year if fecha_inicio else None,
        entity_name=razon_social,
        entity_ruc=ruc,
        source_url=SANCIONES_URL,
        evidence_quote=_build_evidence_quote(razon_social, ruc, tipo_sancion, estado, resolucion),
    )


def _read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "latin-1", "iso-8859-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _normalize_key(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum()).strip()


def _normalize_ruc(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits if len(digits) == 11 else None


def _clean(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _normalize_tipo(value: str | None) -> str | None:
    if not value:
        return None
    upper = value.upper().strip()
    if "DEFINITIVA" in upper or "DEFINITIVO" in upper:
        return "DEFINITIVO"
    if "TEMPORAL" in upper or "TEMPORANEA" in upper:
        return "TEMPORAL"
    if "MULTA" in upper:
        return "MULTA"
    if "SUSPENSION" in upper or "SUSPENDIDA" in upper:
        return "SUSPENSION"
    return value.strip()


def _normalize_estado(value: str | None) -> str | None:
    if not value:
        return None
    upper = value.upper().strip()
    if "NO VIGENTE" in upper or "VENCIDA" in upper or "LEVANTADA" in upper:
        return "NO VIGENTE"
    if "VIGENTE" in upper:
        return "VIGENTE"
    return value.strip()


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    cleaned = value.strip()
    for _fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d-%m-%y"):
        try:
            return date(int(cleaned[-4:]), int(cleaned[-7:-5]), int(cleaned[-10:-8]))
        except (ValueError, IndexError):
            pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d-%m-%y"):
        try:
            from datetime import datetime
            return datetime.strptime(cleaned[:10], fmt).date()
        except ValueError:
            continue
    return None


def _build_evidence_quote(
    razon_social: str | None,
    ruc: str | None,
    tipo: str | None,
    estado: str | None,
    resolucion: str | None,
) -> str:
    estado_text = f" en estado {estado}" if estado else ""
    tipo_text = f" por {tipo}" if tipo else ""
    resolucion_text = f" (Resolución {resolucion})" if resolucion else ""
    return (
        f"OECE reporta sanción {tipo_text}{estado_text} para "
        f"{razon_social or 'empresa sin nombre'} con RUC {ruc or 'desconocido'}"
        f"{resolucion_text}."
    )
