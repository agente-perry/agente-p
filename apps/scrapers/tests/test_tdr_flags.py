from agenteperry.tdr.flags import detect_flags_in_pages
from agenteperry.tdr.models import TdrPage, TdrSeverity


def test_detects_tdr_flags_with_page_and_evidence():
    pages = [
        TdrPage(
            page_number=2,
            text_content="El proveedor debera presentar informe de 500 paginas en formato A3 impreso.",
        ),
        TdrPage(
            page_number=4,
            text_content="Se requiere camioneta 4x4 y certificacion ISO 9001 para el servicio.",
        ),
    ]

    flags = detect_flags_in_pages(pages)
    flag_codes = {flag.flag_code for flag in flags}

    assert "EXCESSIVE_DOCUMENT_REQUIREMENT" in flag_codes
    assert "OBSOLETE_PHYSICAL_FORMAT" in flag_codes
    assert "SPECIFIC_EQUIPMENT_REQUIREMENT" in flag_codes
    assert "EXCESSIVE_CERTIFICATION_REQUIREMENT" in flag_codes
    assert all(flag.page_number in {2, 4} for flag in flags)
    assert all(flag.evidence_quote for flag in flags)


def test_detects_subjective_evaluation_criteria():
    flags = detect_flags_in_pages(
        [TdrPage(page_number=1, text_content="La calidad de la propuesta sera evaluada a criterio del comite.")]
    )

    assert any(flag.flag_code == "SUBJECTIVE_EVALUATION_CRITERIA" for flag in flags)


def test_no_flags_for_plain_traceable_requirement():
    pages = [
        TdrPage(
            page_number=1,
            text_content="El proveedor entregara base de datos estructurada y diccionario de campos.",
        )
    ]

    assert detect_flags_in_pages(pages) == []


def test_severity_is_conservative():
    flags = detect_flags_in_pages([TdrPage(page_number=1, text_content="Se entregara informe final.")])

    assert flags[0].severity == TdrSeverity.LOW
