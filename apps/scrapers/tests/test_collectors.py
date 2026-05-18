import json
from pathlib import Path

from agenteperry.collectors.factory import build_collector
from agenteperry.collectors.ocds import flatten_ocds_release, iter_ocds_releases
from agenteperry.collectors.oece_collector import (
    OeceCategory,
    discover_oece_links,
    iter_oece_rows,
    oece_row_to_result,
)
from agenteperry.collectors.sanciones import (
    SancionesCollector,
    iter_sanciones_rows,
    sancion_row_to_result,
)
from agenteperry.collectors.sunat import iter_sunat_rows, sunat_row_to_result
from agenteperry.sources.catalog import build_default_registry


def test_ocds_jsonl_parser_and_flattening(tmp_path: Path):
    path = tmp_path / "releases.jsonl"
    release = {
        "ocid": "ocds-test-1",
        "date": "2026-01-15T00:00:00Z",
        "buyer": {"id": "PE-CONSUCODE-1055", "name": "Municipalidad Demo"},
        "tender": {"id": "T-1", "procurementMethod": "open", "value": {"amount": 1000}},
        "awards": [
            {
                "id": "A-1",
                "date": "2026-01-20T00:00:00Z",
                "status": "active",
                "value": {"amount": 950.5},
                "suppliers": [{"id": "20987654321", "name": "Proveedor Demo SAC"}],
            }
        ],
        "parties": [
            {
                "id": "PE-CONSUCODE-1055",
                "name": "Municipalidad Demo",
                "roles": ["buyer", "procuringEntity"],
                "identifier": {"id": "1055", "scheme": "PE-CONSUCODE"},
                "additionalIdentifiers": [
                    {"id": "20123456789", "scheme": "PE-RUC", "legalName": "Municipalidad Demo"}
                ],
                "address": {"department": "LIMA"},
            },
            {
                "id": "PE-RUC-2098765",
                "name": "Proveedor Demo SAC",
                "roles": ["supplier", "tenderer"],
                "identifier": {"id": "20987654321", "scheme": "PE-RUC"},
                "address": {},
            },
        ],
    }
    path.write_text(json.dumps(release) + "\n", encoding="utf-8")

    parsed = list(iter_ocds_releases(path))
    results = flatten_ocds_release(parsed[0], path, "abc")

    assert len(results) == 1
    record = results[0].to_record()
    assert record["record_type"] == "contract"
    assert record["entity_ruc"] == "20123456789", f"Expected RUC from parties, got {record['entity_ruc']}"
    assert record["supplier_ruc"] == "20987654321"
    assert record["monto"] == 950.5
    assert record["period_year"] == 2026
    assert record["region"] == "LIMA"


def test_sunat_padron_parser(tmp_path: Path):
    path = tmp_path / "padron.txt"
    path.write_text(
        "20987654321|PROVEEDOR DEMO SAC|ACTIVO|HABIDO|150101|AV.|LIMA||||||||\n",
        encoding="iso-8859-1",
    )

    rows = list(iter_sunat_rows(path))
    result = sunat_row_to_result(rows[0], path, "abc")

    record = result.to_record()
    assert record["record_type"] == "company"
    assert record["entity_ruc"] == "20987654321"
    assert record["entity_name"] == "PROVEEDOR DEMO SAC"
    assert record["region"] == "15"
    assert "ACTIVO" in str(record["evidence_quote"])
    assert record["source_url"] == "https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html"


def test_sunat_padron_parser_invalid_ruc_rejected(tmp_path: Path):
    path = tmp_path / "padron_invalid.txt"
    path.write_text(
        "12345678|EMPRESA CORTA SAC|ACTIVO|HABIDO|150101|AV.|LIMA||||||||\n",
        encoding="iso-8859-1",
    )

    rows = list(iter_sunat_rows(path))
    result = sunat_row_to_result(rows[0], path, "abc")
    record = result.to_record()

    assert record["entity_ruc"] is None
    assert record["external_id"] is None
    assert record["record_type"] == "company"
    assert record["entity_name"] == "EMPRESA CORTA SAC"


def test_sunat_padron_parser_encoding_n_tilde(tmp_path: Path):
    path = tmp_path / "padron_encoding.txt"
    path.write_text(
        "20987654322|COMPAÑIA SEÑOR DEL VALLE SAC|ACTIVO|HABIDO|150101|AV.|LIMA||||||||\n",
        encoding="iso-8859-1",
    )

    rows = list(iter_sunat_rows(path))
    result = sunat_row_to_result(rows[0], path, "abc")
    record = result.to_record()

    assert record["entity_ruc"] == "20987654322"
    assert record["entity_name"] == "COMPAÑIA SEÑOR DEL VALLE SAC"
    assert "COMPAÑIA" in str(record["evidence_quote"])


def test_oece_procedimientos_parser_maps_common_columns(tmp_path: Path):
    path = tmp_path / "oece_procedimientos.csv"
    path.write_text(
        "codigo_proceso,entidad,ruc_entidad,proveedor,ruc_proveedor,monto,fecha,region,tipo_proceso,objeto\n"
        "LP-1,Municipalidad Demo,20123456789,Proveedor Demo SAC,20987654321,1234.50,2026-02-03,Lima,Licitacion,Obra vial\n",
        encoding="utf-8",
    )

    rows = iter_oece_rows(path)
    result = oece_row_to_result(rows[0], OeceCategory.PROCEDIMIENTOS, path, "abc")

    record = result.to_record()
    assert record["record_type"] == "contract"
    assert record["external_id"] == "procedimientos:LP-1:20987654321"
    assert record["entity_ruc"] == "20123456789"
    assert record["supplier_ruc"] == "20987654321"
    assert record["monto"] == 1234.50
    assert record["fecha"] == "2026-02-03"
    assert record["parsed_data"]["tipo_proceso"] == "Licitacion"


def test_oece_ordenes_compra_parser_maps_purchase_order(tmp_path: Path):
    path = tmp_path / "oece_ordenes.csv"
    path.write_text(
        "orden_compra,entidad,ruc_entidad,proveedor,ruc_proveedor,importe,fecha,departamento\n"
        "OC-77,Gobierno Regional Demo,20111111111,Servicios Demo SAC,20999999999,8500,03/04/2026,Cusco\n",
        encoding="utf-8",
    )

    rows = iter_oece_rows(path)
    result = oece_row_to_result(rows[0], OeceCategory.ORDENES_COMPRA, path, "abc")
    record = result.to_record()

    assert record["record_type"] == "purchase_order"
    assert record["entity_name"] == "Gobierno Regional Demo"
    assert record["supplier_name"] == "Servicios Demo SAC"
    assert record["monto"] == 8500.0
    assert record["region"] == "Cusco"


def test_oece_comites_parser_maps_committee_member(tmp_path: Path):
    path = tmp_path / "oece_comites.csv"
    path.write_text(
        "codigo_proceso,entidad,miembro_comite,cargo_comite\n"
        "AS-9,Municipalidad Demo,Juan Perez,Presidente\n",
        encoding="utf-8",
    )

    rows = iter_oece_rows(path)
    result = oece_row_to_result(rows[0], OeceCategory.COMITES, path, "abc")
    record = result.to_record()

    assert record["record_type"] == "committee_member"
    assert record["external_id"] == "comites:AS-9:Juan Perez"
    assert record["parsed_data"]["miembro_comite"] == "Juan Perez"
    assert "comite" in str(record["evidence_quote"])


def test_oece_static_link_discovery_filters_csv_links():
    html = '<a href="/files/procedimientos_2026.csv">CSV</a><a href="/files/comites_2026.xlsx">XLSX</a>'

    links = discover_oece_links(html, "https://contratacionesabiertas.oece.gob.pe/descargas")

    assert "https://contratacionesabiertas.oece.gob.pe/files/procedimientos_2026.csv" in links
    assert "https://contratacionesabiertas.oece.gob.pe/files/comites_2026.xlsx" in links


def test_sanciones_csv_parser_maps_common_columns(tmp_path: Path):
    path = tmp_path / "sanciones.csv"
    path.write_text(
        "ruc,razon_social,resolucion,tipo_sancion,fecha_inicio,fecha_fin,estado,infraccion,entidad\n"
        "20987654321,EMPRESA DEMO SAC,RES-2026-001,DEFINITIVA,2026-01-15,2028-01-15,VIGENTE,fraude en contratacion,OSCE\n",
        encoding="utf-8",
    )

    rows = iter_sanciones_rows(path)
    result = sancion_row_to_result(rows[0], path, "abc")

    record = result.to_record()
    assert record["record_type"] == "sanction"
    assert record["entity_ruc"] == "20987654321"
    assert record["entity_name"] == "EMPRESA DEMO SAC"
    assert record["parsed_data"]["tipo_sancion"] == "DEFINITIVO"
    assert record["parsed_data"]["estado"] == "VIGENTE"
    assert record["source_code"] == "contraloria_sanciones"
    assert "VIGENTE" in record["evidence_quote"]


def test_sanciones_parser_normalizes_tipo_and_estado(tmp_path: Path):
    path = tmp_path / "sanciones2.csv"
    path.write_text(
        "ruc,razon_social,tipo,estado,resolucion,fecha_inicio,infraccion,entidad\n"
        "20987654321,EMPRESA TEST,INHABILITACION TEMPORAL,NO VIGENTE,RES-2,2025-01-01,obra publica mal ejecutada,OSCE\n",
        encoding="utf-8",
    )

    rows = iter_sanciones_rows(path)
    result = sancion_row_to_result(rows[0], path, "abc")
    record = result.to_record()

    assert record["parsed_data"]["tipo_sancion"] == "TEMPORAL"
    assert record["parsed_data"]["estado"] == "NO VIGENTE"


def test_sanciones_csv_with_semicolon_delimiter(tmp_path: Path):
    path = tmp_path / "sanciones3.csv"
    path.write_text(
        "ruc;razon_social;resolucion;tipo_sancion;fecha_inicio;fecha_fin;estado;infraccion\n"
        "20987654321;EMPRESA PUNTOCOM;RES-3;MULTA;2026-03-01;;VIGENTE;incumplimiento contractual\n",
        encoding="latin-1",
    )

    rows = iter_sanciones_rows(path)
    result = sancion_row_to_result(rows[0], path, "checksum123")
    record = result.to_record()

    assert record["entity_ruc"] == "20987654321"
    assert record["parsed_data"]["tipo_sancion"] == "MULTA"
    assert record["parsed_data"]["estado"] == "VIGENTE"
    assert record["checksum"] == "checksum123"


def test_factory_builds_sanciones_collector():
    registry = build_default_registry()
    source = registry.get("contraloria_sanciones")
    assert source is not None

    collector = build_collector(source)
    assert isinstance(collector, SancionesCollector)


def test_factory_builds_all_p0_collectors():
    registry = build_default_registry()
    codes = ["ocds_peru", "sunat_padron", "seace_oece", "contraloria_sanciones"]
    for code in codes:
        source = registry.get(code)
        assert source is not None, f"Source {code} not found in registry"
        collector = build_collector(source)
        assert collector is not None, f"Collector for {code} is None"
