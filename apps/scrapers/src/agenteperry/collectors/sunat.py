"""SUNAT Padron Reducido collector and parser."""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from agenteperry.collectors.base import BulkDownloadCollector, CollectionResult

SUNAT_PADRON_URL = "https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html"

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


class SunatPadronCollector(BulkDownloadCollector):
    """Collect and parse SUNAT's reduced RUC registry.

    Accepts either a direct ZIP/TXT path via ``input_path``,
    or a ``download_url`` which will be auto-discovered from
    ``SUNAT_PADRON_URL`` if not provided.
    """

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
                raise ValueError("SUNAT collector needs input_path or download_dir")
            resolved_url = download_url or self._discover_download_url()
            if not resolved_url:
                raise ValueError(
                    f"Could not discover SUNAT padron URL. "
                    f"Pass --download-url directly or download manually from {SUNAT_PADRON_URL}"
                )
            filename = self._build_filename(resolved_url)
            input_path = self.download(resolved_url, download_dir, filename=filename)

        checksum = self.calculate_checksum(input_path.read_bytes())
        results: list[CollectionResult] = []
        for row in iter_sunat_rows(input_path):
            results.append(sunat_row_to_result(row, input_path, checksum))
            if limit is not None and len(results) >= limit:
                return results
        return results

    def _discover_download_url(self) -> str | None:
        """Find the actual padron ZIP URL from the SUNAT download page."""
        try:
            with urllib.request.urlopen(SUNAT_PADRON_URL, timeout=30) as response:
                html = response.read().decode("utf-8", errors="replace")
        except OSError:
            return None

        href_patterns = [
            r"href=['\"]([^'\"]*mrc137[^\"']+\.zip[^'\"]*)['\"]",
            r"href=['\"]([^'\"]*padron[^\"']+\.zip[^'\"]*)['\"]",
            r"(https?://www\.sunat\.gob\.pe/descargaPRR/[^\"'<\s]+\.zip)",
        ]
        for pattern in href_patterns:
            match = re.search(pattern, html, re.I)
            if match:
                url = match.group(1).split("?")[0].split("#")[0]
                return url.strip()
        return None

    def _build_filename(self, url: str) -> str:
        path = urllib.parse.urlparse(url).path
        name = path.split("/")[-1] if path else "sunat_padron.zip"
        return name if name.endswith(".zip") or name.endswith(".txt") else "sunat_padron.zip"


def iter_sunat_rows(path: Path) -> Iterator[dict[str, str]]:
    """Yield normalized SUNAT rows from ZIP or TXT files."""
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            text_name = _first_text_member(archive)
            with archive.open(text_name) as raw_file:
                for raw_line in raw_file:
                    yield _parse_sunat_line(raw_line.decode("iso-8859-1", errors="replace"))
        return

    with path.open(encoding="iso-8859-1", errors="replace") as file_obj:
        for line in file_obj:
            yield _parse_sunat_line(line)


def sunat_row_to_result(row: dict[str, str], raw_path: Path | None = None, checksum: str | None = None) -> CollectionResult:
    ruc = _normalize_ruc(row.get("ruc"))
    razon_social = _clean(row.get("razon_social"))
    estado = _clean(row.get("estado"))
    condicion = _clean(row.get("condicion"))
    ubigeo = _clean(row.get("ubigeo"))
    address = _build_address(row)

    return CollectionResult(
        source_code="sunat_padron",
        external_id=ruc,
        record_type="company",
        raw_data=row,
        parsed_data={
            "ruc": ruc,
            "razon_social": razon_social,
            "estado": estado,
            "condicion": condicion,
            "ubigeo": ubigeo,
            "domicilio_fiscal": address,
        },
        raw_path=raw_path,
        checksum=checksum,
        content_type="text/plain",
        entity_name=razon_social,
        entity_ruc=ruc,
        region=ubigeo[:2] if ubigeo and len(ubigeo) >= 2 else None,
        source_url=SUNAT_PADRON_URL,
        evidence_quote=f"SUNAT registra a {razon_social or 'empresa sin nombre'} con RUC {ruc or 'sin RUC'} en estado {estado or 'sin estado'}.",
    )


def _first_text_member(archive: zipfile.ZipFile) -> str:
    for name in archive.namelist():
        lowered = name.lower()
        if lowered.endswith((".txt", ".csv")) and not lowered.endswith("/"):
            return name
    raise ValueError("SUNAT ZIP does not contain a TXT/CSV member")


def _parse_sunat_line(line: str) -> dict[str, str]:
    parts = [part.strip() for part in line.rstrip("\n\r").split("|")]
    if len(parts) == 1:
        parts = [part.strip() for part in line.rstrip("\n\r").split(",")]
    return {column: parts[index] if index < len(parts) else "" for index, column in enumerate(SUNAT_COLUMNS)}


def _normalize_ruc(value: str | None) -> str | None:
    digits = "".join(ch for ch in value or "" if ch.isdigit())
    return digits if len(digits) == 11 else None


def _clean(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _build_address(row: dict[str, str]) -> str | None:
    parts = [
        row.get("tipo_via"),
        row.get("nombre_via"),
        row.get("numero"),
        row.get("interior"),
        row.get("lote"),
        row.get("departamento"),
        row.get("manzana"),
        row.get("kilometro"),
    ]
    cleaned = [part.strip() for part in parts if part and part.strip()]
    return " ".join(cleaned) if cleaned else None
