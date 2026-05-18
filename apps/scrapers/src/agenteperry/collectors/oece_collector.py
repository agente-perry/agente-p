"""OECE/SEACE open-data collector.

The legacy notes are explicit: use direct downloads/XHR endpoints and avoid
driving the Pentaho/Angular UI. This collector supports local exports, direct
download URLs captured from DevTools, and lightweight link discovery from the
public downloads page when static links are present.
"""

from __future__ import annotations

import csv
import re
import urllib.parse
import urllib.request
import zipfile
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from agenteperry.collectors.base import BulkDownloadCollector, CollectionResult

OECE_DOWNLOADS_URL = "https://contratacionesabiertas.oece.gob.pe/descargas"
OECE_PENTAHO_PORTAL_URL = (
    "https://bi.seace.gob.pe/pentaho/api/repos/:public:portal:datosabiertos.html/content"
    "?userid=public&password=key"
)


class OeceCategory(StrEnum):
    """Known OECE/SEACE data categories from the legacy source map."""

    PAC = "pac"
    PROCEDIMIENTOS = "procedimientos"
    CONVOCATORIAS = "convocatorias"
    CONTRATOS = "contratos"
    ORDENES_COMPRA = "ordenes_compra"
    PROVEEDORES = "proveedores"
    CONSORCIOS = "consorcios"
    ENTIDADES = "entidades"
    COMITES = "comites"
    PRONUNCIAMIENTOS = "pronunciamientos"


OECE_CATEGORY_LABELS: dict[OeceCategory, str] = {
    OeceCategory.PAC: "Plan Anual de Contrataciones",
    OeceCategory.PROCEDIMIENTOS: "Procedimientos adjudicados",
    OeceCategory.CONVOCATORIAS: "Convocatorias",
    OeceCategory.CONTRATOS: "Contratos",
    OeceCategory.ORDENES_COMPRA: "Ordenes de compra",
    OeceCategory.PROVEEDORES: "Proveedores",
    OeceCategory.CONSORCIOS: "Consorcios",
    OeceCategory.ENTIDADES: "Entidades contratantes",
    OeceCategory.COMITES: "Miembros de comite",
    OeceCategory.PRONUNCIAMIENTOS: "Pronunciamientos",
}

CONTRACT_LIKE_CATEGORIES = {
    OeceCategory.PROCEDIMIENTOS,
    OeceCategory.CONVOCATORIAS,
    OeceCategory.CONTRATOS,
}


class OeceCollector(BulkDownloadCollector):
    """Download and normalize OECE/SEACE CSV/XLSX exports."""

    def collect(
        self,
        download_dir: Path | None = None,
        input_path: Path | None = None,
        download_url: str | None = None,
        category: str | None = None,
        year: int | None = None,
        file_format: str = "csv",
        discover_url: str = OECE_DOWNLOADS_URL,
        limit: int | None = None,
        **_: Any,
    ) -> list[CollectionResult]:
        parsed_category = parse_oece_category(category)
        if input_path is None:
            if download_dir is None:
                raise ValueError("OECE collector needs download_dir when no input_path is provided")
            resolved_url = download_url or discover_oece_download_url(
                category=parsed_category,
                year=year,
                file_format=file_format,
                discover_url=discover_url,
            )
            if not resolved_url:
                raise ValueError(
                    "OECE download URL not found. Open DevTools Network on "
                    f"{OECE_DOWNLOADS_URL}, filter by CSV/XLSX, then pass --download-url. "
                    f"Pentaho portal reference: {OECE_PENTAHO_PORTAL_URL}"
                )
            filename = build_oece_filename(parsed_category, year, resolved_url)
            input_path = self.download(resolved_url, download_dir, filename=filename)

        checksum = self.calculate_checksum(input_path.read_bytes())
        rows = iter_oece_rows(input_path)
        results: list[CollectionResult] = []
        for row in rows:
            results.append(oece_row_to_result(row, parsed_category, input_path, checksum))
            if limit is not None and len(results) >= limit:
                return results
        return results


def parse_oece_category(value: str | None) -> OeceCategory:
    if not value:
        return OeceCategory.PROCEDIMIENTOS
    normalized = value.strip().lower().replace("-", "_")
    try:
        return OeceCategory(normalized)
    except ValueError as exc:
        valid = ", ".join(category.value for category in OeceCategory)
        raise ValueError(f"Unknown OECE category '{value}'. Valid categories: {valid}") from exc


def build_oece_filename(category: OeceCategory, year: int | None, url: str) -> str:
    suffix = Path(urllib.parse.urlparse(url).path).suffix or ".csv"
    year_part = f"_{year}" if year else ""
    return f"oece_{category.value}{year_part}{suffix}"


def discover_oece_download_url(
    category: OeceCategory,
    year: int | None = None,
    file_format: str = "csv",
    discover_url: str = OECE_DOWNLOADS_URL,
) -> str | None:
    """Find a static CSV/XLSX link if the download page exposes one."""
    with urllib.request.urlopen(discover_url, timeout=60) as response:
        html = response.read().decode("utf-8", errors="replace")
    candidates = discover_oece_links(html, discover_url)
    category_text = category.value.replace("_", "")
    requested_format = file_format.strip(".").lower()
    year_text = str(year) if year else None
    for url in candidates:
        normalized = _normalize_key(url)
        suffix = Path(urllib.parse.urlparse(url).path).suffix.lower().strip(".")
        if requested_format and suffix != requested_format:
            continue
        if category_text not in normalized:
            continue
        if year_text and year_text not in normalized:
            continue
        return url
    return None


def discover_oece_links(html: str, base_url: str = OECE_DOWNLOADS_URL) -> list[str]:
    """Extract direct CSV/XLSX links from HTML or Angular templates."""
    links: list[str] = []
    for match in re.finditer(r"(?:href|src)=['\"]([^'\"]+\.(?:csv|xlsx)(?:\?[^'\"]*)?)['\"]", html, re.I):
        links.append(urllib.parse.urljoin(base_url, match.group(1)))
    for match in re.finditer(r"https?://[^'\"\s]+\.(?:csv|xlsx)(?:\?[^'\"\s]*)?", html, re.I):
        links.append(match.group(0))
    return sorted(set(links))


def iter_oece_rows(path: Path) -> list[dict[str, str]]:
    """Read OECE/SEACE CSV, TXT, or basic XLSX exports."""
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return _read_xlsx_rows(path)
    return _read_csv_rows(path)


def oece_row_to_result(
    row: dict[str, str],
    category: OeceCategory = OeceCategory.PROCEDIMIENTOS,
    raw_path: Path | None = None,
    checksum: str | None = None,
) -> CollectionResult:
    process_code = _pick(row, "codigo_proceso", "codigo", "id_proceso", "n_proceso", "proceso", "nomenclatura")
    entity_name = _pick(row, "entidad", "nombre_entidad", "comprador", "entidad_contratante")
    entity_ruc = _normalize_ruc(_pick(row, "ruc_entidad", "entidad_ruc", "ruccomprador", "ruc_entidad_contratante"))
    supplier_name = _pick(row, "proveedor", "contratista", "adjudicatario", "ganador", "razon_social_proveedor")
    supplier_ruc = _normalize_ruc(_pick(row, "ruc_proveedor", "proveedor_ruc", "ruccontratista", "ruc_adjudicatario", "ruc"))
    amount = _parse_amount(_pick(row, "monto", "monto_adjudicado", "valor_adjudicado", "importe", "valor_referencial", "valor_estimado"))
    event_date = _parse_date(_pick(row, "fecha", "fecha_adjudicacion", "fecha_buena_pro", "fecha_publicacion", "fecha_convocatoria", "fecha_contrato"))
    region = _pick(row, "region", "departamento", "departamento_entidad")
    committee_member = _pick(row, "miembro_comite", "integrante_comite", "nombre_miembro", "funcionario", "nombres")
    committee_role = _pick(row, "cargo_comite", "rol", "cargo", "tipo_miembro")
    external_id = _build_external_id(category, process_code, supplier_ruc, committee_member, row)

    parsed_data = {
        "category": category.value,
        "category_label": OECE_CATEGORY_LABELS[category],
        "codigo_proceso": process_code,
        "tipo_proceso": _pick(row, "tipo_proceso", "modalidad", "procedimiento", "tipo_seleccion"),
        "objeto": _pick(row, "objeto", "descripcion", "objeto_contractual", "nomenclatura"),
        "contrato": _pick(row, "contrato", "numero_contrato", "codigo_contrato"),
        "orden_compra": _pick(row, "orden_compra", "numero_orden", "ocam", "orden"),
        "comite": _pick(row, "comite", "codigo_comite", "numero_comite"),
        "miembro_comite": committee_member,
        "cargo_comite": committee_role,
        "consorcio": _pick(row, "consorcio", "nombre_consorcio"),
        "risk_hints": _row_risk_hints(row),
    }

    return CollectionResult(
        source_code="seace_oece",
        external_id=external_id,
        record_type=_record_type_for_category(category),
        raw_data=row,
        parsed_data=parsed_data,
        raw_path=raw_path,
        checksum=checksum,
        content_type=_content_type(raw_path),
        period_year=event_date.year if event_date else _parse_year(row),
        region=region,
        entity_name=entity_name,
        entity_ruc=entity_ruc,
        supplier_name=supplier_name,
        supplier_ruc=supplier_ruc,
        monto=amount,
        fecha=event_date,
        source_url=OECE_DOWNLOADS_URL,
        evidence_quote=_build_evidence_quote(category, entity_name, supplier_name, process_code, amount, committee_member),
    )


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    text = _read_text(path)
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;|\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    return [
        {str(key).strip(): (value or "").strip() for key, value in row.items()}
        for row in reader
    ]


def _read_xlsx_rows(path: Path) -> list[dict[str, str]]:
    """Read first worksheet from an XLSX using stdlib XML parsing."""
    with zipfile.ZipFile(path) as archive:
        shared_strings = _read_shared_strings(archive)
        sheet_name = _first_sheet_name(archive)
        sheet_xml = archive.read(sheet_name)
    root = ElementTree.fromstring(sheet_xml)
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows: list[list[str]] = []
    for row in root.findall(".//x:sheetData/x:row", namespace):
        values: list[str] = []
        for cell in row.findall("x:c", namespace):
            values.append(_cell_value(cell, shared_strings, namespace))
        if values:
            rows.append(values)
    if not rows:
        return []
    headers = [header.strip() for header in rows[0]]
    return [
        {header: values[index].strip() if index < len(values) else "" for index, header in enumerate(headers)}
        for values in rows[1:]
    ]


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall("x:si", namespace):
        texts = [node.text or "" for node in item.findall(".//x:t", namespace)]
        strings.append("".join(texts))
    return strings


def _first_sheet_name(archive: zipfile.ZipFile) -> str:
    candidates = sorted(
        name for name in archive.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)
    )
    if not candidates:
        raise ValueError("XLSX has no worksheets")
    return candidates[0]


def _cell_value(cell: ElementTree.Element, shared_strings: list[str], namespace: dict[str, str]) -> str:
    value_node = cell.find("x:v", namespace)
    if value_node is None or value_node.text is None:
        inline_text = cell.find(".//x:t", namespace)
        return inline_text.text if inline_text is not None and inline_text.text else ""
    raw_value = value_node.text
    if cell.attrib.get("t") == "s":
        try:
            return shared_strings[int(raw_value)]
        except (IndexError, ValueError):
            return raw_value
    return raw_value


def _read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _record_type_for_category(category: OeceCategory) -> str:
    if category in CONTRACT_LIKE_CATEGORIES:
        return "contract"
    if category == OeceCategory.ORDENES_COMPRA:
        return "purchase_order"
    if category == OeceCategory.PROVEEDORES:
        return "company"
    if category == OeceCategory.ENTIDADES:
        return "public_entity"
    if category == OeceCategory.COMITES:
        return "committee_member"
    if category == OeceCategory.PAC:
        return "annual_plan"
    if category == OeceCategory.PRONUNCIAMIENTOS:
        return "pronouncement"
    return category.value


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


def _parse_year(row: dict[str, str]) -> int | None:
    year = _pick(row, "anio", "año", "year", "periodo")
    if not year:
        return None
    try:
        return int(year[:4])
    except ValueError:
        return None


def _build_external_id(
    category: OeceCategory,
    process_code: str | None,
    supplier_ruc: str | None,
    committee_member: str | None,
    row: dict[str, str],
) -> str:
    explicit = _pick(row, "id", "uuid", "codigo", "codigo_registro")
    parts = [category.value, process_code or explicit, supplier_ruc, committee_member]
    cleaned = [part for part in parts if part]
    if cleaned:
        return ":".join(cleaned)
    return f"{category.value}:{abs(hash(tuple(sorted(row.items()))))}"


def _row_risk_hints(row: dict[str, str]) -> list[str]:
    values = " ".join(row.values()).lower()
    hints: list[str] = []
    if "contratacion directa" in values or "contratación directa" in values:
        hints.append("contratacion_directa")
    if "unico postor" in values or "único postor" in values or "postor unico" in values:
        hints.append("unico_postor")
    if "desierto" in values:
        hints.append("proceso_desierto")
    return hints


def _content_type(path: Path | None) -> str:
    if path and path.suffix.lower() == ".xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return "text/csv"


def _build_evidence_quote(
    category: OeceCategory,
    entity: str | None,
    supplier: str | None,
    process_code: str | None,
    amount: float | None,
    committee_member: str | None,
) -> str:
    label = OECE_CATEGORY_LABELS[category]
    amount_text = f" por {amount:.2f}" if amount is not None else ""
    if category == OeceCategory.COMITES:
        return f"OECE/SEACE registra a {committee_member or 'miembro no identificado'} en el comite del proceso {process_code or 'sin codigo'}."
    if category in CONTRACT_LIKE_CATEGORIES or category == OeceCategory.ORDENES_COMPRA:
        return f"OECE/SEACE registra {label.lower()} {process_code or 'sin codigo'} entre {entity or 'entidad no identificada'} y {supplier or 'proveedor no identificado'}{amount_text}."
    return f"OECE/SEACE registra {label.lower()} para {entity or supplier or process_code or 'registro no identificado'}."
