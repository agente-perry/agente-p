"""Source registry and catalog definitions."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SourcePriority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class SourceStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    PAUSED = "paused"
    DEPRECATED = "deprecated"


class SourceType(StrEnum):
    API = "api"
    BULK_DOWNLOAD = "bulk_download"
    PLAYWRIGHT = "playwright"
    FORM_SCRAPING = "form_scraping"
    CKAN = "ckan"
    MANUAL = "manual"
    REFERENCE = "reference"


class SourceCatalogEntry(BaseModel):
    """Definition of a public data source."""

    source_code: str = Field(pattern=r"^[a-z0-9_]+$")
    source_name: str
    source_url: str | None = None
    source_type: SourceType
    priority: SourcePriority
    status: SourceStatus = SourceStatus.PLANNED
    license_note: str | None = None
    update_freq: str | None = None
    owner: str | None = None
    method_notes: str | None = None
    fields: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceRegistry:
    """In-memory registry of all known sources."""

    def __init__(self) -> None:
        self._sources: dict[str, SourceCatalogEntry] = {}

    def register(self, entry: SourceCatalogEntry) -> None:
        self._sources[entry.source_code] = entry

    def get(self, code: str) -> SourceCatalogEntry | None:
        return self._sources.get(code)

    def list_all(self) -> list[SourceCatalogEntry]:
        return list(self._sources.values())

    def by_priority(self, priority: SourcePriority) -> list[SourceCatalogEntry]:
        return [s for s in self._sources.values() if s.priority == priority]

    def by_status(self, status: SourceStatus) -> list[SourceCatalogEntry]:
        return [s for s in self._sources.values() if s.status == status]

    def active_p0(self) -> list[SourceCatalogEntry]:
        return [
            s for s in self._sources.values()
            if s.priority == SourcePriority.P0 and s.status == SourceStatus.ACTIVE
        ]


def build_default_registry() -> SourceRegistry:
    """Build registry with all 24 sources from the legacy analysis."""
    registry = SourceRegistry()

    sources = [
        SourceCatalogEntry(
            source_code="ocds_peru",
            source_name="OCDS Peru — Open Contracting Data Registry",
            source_url="https://data.open-contracting.org/es/publication/135",
            source_type=SourceType.BULK_DOWNLOAD,
            priority=SourcePriority.P0,
            owner="Anthony",
            method_notes="Direct download JSONL.gz/CSV by year. Full JSON ~2GB.",
            fields=["ocid", "tender", "awards", "contracts", "buyers", "suppliers"],
            red_flags=["single_tenderer", "direct_award", "value_delta"],
        ),
        SourceCatalogEntry(
            source_code="sunat_padron",
            source_name="SUNAT — Padron Reducido del RUC",
            source_url="https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html",
            source_type=SourceType.BULK_DOWNLOAD,
            priority=SourcePriority.P0,
            owner="Anthony",
            method_notes="ZIP download. Parse TXT pipe-delimited ISO-8859-1. ~14.5M records.",
            fields=["ruc", "razon_social", "estado", "condicion", "ubigeo"],
            red_flags=["no_habido", "baja_definitiva", "domicilio_compartido"],
        ),
        SourceCatalogEntry(
            source_code="seace_oece",
            source_name="SEACE/OECE — Portal Datos Abiertos",
            source_url="https://bi.seace.gob.pe/pentaho/api/repos/:public:portal:datosabiertos.html/content?userid=public&password=key",
            source_type=SourceType.BULK_DOWNLOAD,
            priority=SourcePriority.P0,
            owner="John",
            method_notes="Direct download CSV/XLSX from OECE/Pentaho by category/year. Use DevTools XHR; do not depend on UI.",
            fields=[
                "codigo_proceso",
                "entidad",
                "ruc_entidad",
                "proveedor",
                "ruc_proveedor",
                "monto",
                "fecha",
                "tipo_proceso",
                "objeto",
                "region",
                "comite",
                "contrato",
                "orden_compra",
            ],
            red_flags=[
                "proveedor_recurrente",
                "concentracion",
                "contratacion_directa",
                "unico_postor",
                "fraccionamiento",
                "comite_repetido",
                "monto_atipico",
            ],
            metadata={
                "download_portal": "https://contratacionesabiertas.oece.gob.pe/descargas",
                "categories": [
                    "pac",
                    "procedimientos",
                    "convocatorias",
                    "contratos",
                    "ordenes_compra",
                    "proveedores",
                    "consorcios",
                    "entidades",
                    "comites",
                    "pronunciamientos",
                ],
            },
        ),
        SourceCatalogEntry(
            source_code="contraloria_sanciones",
            source_name="Contraloria — Registro de Sanciones",
            source_url="https://www.gob.pe/institucion/contraloria/informes-publicaciones/2706979-registro-de-sanciones-inscritas-y-vigentes",
            source_type=SourceType.PLAYWRIGHT,
            priority=SourcePriority.P0,
            owner="John",
            method_notes="Playwright download intercept XLSX. React SPA.",
            fields=["dni", "nombres", "tipo_sancion", "vigencia", "entidad"],
            red_flags=["funcionario_sancionado", "inhabilitado_contratando"],
        ),
        SourceCatalogEntry(
            source_code="ley_32069",
            source_name="Ley 32069 — Ley General de Contrataciones Publicas",
            source_url="https://www.gob.pe/institucion/oece/colecciones/45029-ley-n-32069-ley-general-de-contrataciones-publicas-y-su-reglamento",
            source_type=SourceType.REFERENCE,
            priority=SourcePriority.P0,
            status=SourceStatus.ACTIVE,
            owner="Miguel",
            method_notes="PDF legal reference. Index for RAG legal.",
            fields=["articulo", "texto", "modalidad", "impedimento", "sancion"],
        ),
        SourceCatalogEntry(
            source_code="sunat_multi_ruc",
            source_name="SUNAT — Consulta Multiple de RUC",
            source_url="https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsmulruc/jrmS00Alias",
            source_type=SourceType.FORM_SCRAPING,
            priority=SourcePriority.P1,
            owner="Anthony",
            method_notes="Form POST with ZIP file. CAPTCHA. Max 100 RUC. Semi-manual.",
            fields=["ruc", "razon_social", "estado", "actividad_economica"],
        ),
        SourceCatalogEntry(
            source_code="cgr_informes",
            source_name="CGR — Buscador de Informes de Control",
            source_url="https://appbp.contraloria.gob.pe/BuscadorCGR/informes/Avanzado.html",
            source_type=SourceType.PLAYWRIGHT,
            priority=SourcePriority.P1,
            owner="John",
            method_notes="Playwright XHR intercept + PDF. Angular/jQuery. Selective only.",
            fields=["numero_informe", "entidad", "fecha", "tipo_control", "personas"],
            red_flags=["entidad_con_observaciones", "funcionario_mencionado"],
        ),
        SourceCatalogEntry(
            source_code="sidji_dji",
            source_name="SIDJI — Declaraciones Juradas de Intereses",
            source_url="https://appdji.contraloria.gob.pe/djic/",
            source_type=SourceType.PLAYWRIGHT,
            priority=SourcePriority.P1,
            owner="Miguel",
            method_notes="On-demand only. CAPTCHA. No mass scraping.",
            fields=["funcionario", "cargo", "entidad", "vinculos", "familiares"],
            red_flags=["conflicto_interes", "familiar_proveedor"],
        ),
        SourceCatalogEntry(
            source_code="mef_datos_abiertos",
            source_name="MEF — Datos Abiertos",
            source_url="https://datosabiertos.mef.gob.pe/dataset",
            source_type=SourceType.CKAN,
            priority=SourcePriority.P1,
            owner="Anthony",
            method_notes="CKAN API. package_list / package_search / package_show.",
            fields=["pim", "devengado", "girado", "entidad", "proyecto"],
            red_flags=["alto_gasto_sin_contrato", "ejecucion_sospechosa"],
        ),
        SourceCatalogEntry(
            source_code="onpe_claridad",
            source_name="ONPE — Claridad",
            source_url="https://claridadportal.onpe.gob.pe/",
            source_type=SourceType.PLAYWRIGHT,
            priority=SourcePriority.P1,
            owner="Noelia",
            method_notes="XHR intercept. Search by RUC/DNI/org.",
            fields=["aportante", "organizacion_politica", "monto", "fecha", "campana"],
            red_flags=["proveedor_aportante", "contrato_post_aporte"],
        ),
        SourceCatalogEntry(
            source_code="jne_voto_informado",
            source_name="JNE — Voto Informado",
            source_url="https://votoinformado.jne.gob.pe/",
            source_type=SourceType.PLAYWRIGHT,
            priority=SourcePriority.P1,
            owner="Noelia",
            method_notes="XHR intercept Angular SPA.",
            fields=["candidato", "partido", "experiencia", "sentencias"],
        ),
        SourceCatalogEntry(
            source_code="jne_plataforma",
            source_name="JNE — Plataforma Electoral",
            source_url="https://plataformaelectoral.jne.gob.pe/",
            source_type=SourceType.PLAYWRIGHT,
            priority=SourcePriority.P1,
            owner="Noelia",
            method_notes="XHR intercept.",
            fields=["expediente", "candidato", "organizacion"],
        ),
        SourceCatalogEntry(
            source_code="congreso_leyes",
            source_name="Congreso — Archivo Digital de Legislacion",
            source_url="https://www.leyes.congreso.gob.pe/",
            source_type=SourceType.FORM_SCRAPING,
            priority=SourcePriority.P1,
            owner="Miguel",
            method_notes="ASP.NET WebForms. HTML table + PDF. Index for RAG.",
            fields=["numero_norma", "titulo", "fecha", "texto"],
        ),
        SourceCatalogEntry(
            source_code="ojo_publico_funes",
            source_name="Ojo Publico — FUNES",
            source_url="https://ojo-publico.com/especiales/funes/metodologia.html",
            source_type=SourceType.REFERENCE,
            priority=SourcePriority.P1,
            status=SourceStatus.ACTIVE,
            owner="John",
            method_notes="Methodology reference. Do not copy data. Cite only.",
        ),
        SourceCatalogEntry(
            source_code="open_contracting_memoria",
            source_name="Open Contracting — Memoria contra la corrupcion",
            source_url="https://www.open-contracting.org/es/2020/09/10/memoria-contra-la-corrupcion-datos-y-algoritmos-para-investigar-compras-publicas/",
            source_type=SourceType.REFERENCE,
            priority=SourcePriority.P1,
            status=SourceStatus.ACTIVE,
            owner="Anthony",
            method_notes="Methodology reference.",
        ),
        SourceCatalogEntry(
            source_code="convoca_contrataciones",
            source_name="Convoca — Contrataciones Publicas",
            source_url="https://convoca.pe/tags/contrataciones-publicas",
            source_type=SourceType.FORM_SCRAPING,
            priority=SourcePriority.P1,
            owner="Noelia",
            method_notes="Drupal 9. Save only URL/title/snippet. Respect robots/TOS.",
            fields=["url", "titulo", "fecha", "resumen"],
        ),
        SourceCatalogEntry(
            source_code="sunarp_conoce",
            source_name="SUNARP — Conoce Aqui",
            source_url="https://conoce-aqui.sunarp.gob.pe/",
            source_type=SourceType.MANUAL,
            priority=SourcePriority.P2,
            owner="John",
            method_notes="Requires DNI/date/partida. No mass scraping. Manual only.",
        ),
        SourceCatalogEntry(
            source_code="sunarp_sprl",
            source_name="SUNARP — SPRL",
            source_url="https://sprl.sunarp.gob.pe/",
            source_type=SourceType.MANUAL,
            priority=SourcePriority.P3,
            owner="John",
            method_notes="Paid access. Review TOS first.",
        ),
        SourceCatalogEntry(
            source_code="poder_judicial",
            source_name="Poder Judicial",
            source_url="https://www.pj.gob.pe/",
            source_type=SourceType.MANUAL,
            priority=SourcePriority.P3,
            owner="Miguel",
            method_notes="Only firm public sentences. Human review required.",
        ),
        SourceCatalogEntry(
            source_code="ministerio_publico",
            source_name="Ministerio Publico",
            source_url="https://www.gob.pe/mpfn",
            source_type=SourceType.MANUAL,
            priority=SourcePriority.P3,
            owner="Miguel",
            method_notes="Official notes only. No automation of sensitive data.",
        ),
    ]

    for source in sources:
        registry.register(source)

    return registry
