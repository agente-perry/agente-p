"""Unit tests for InvestigativeQueries (neo4j_queries.py) — SPEC-0012.

All tests inject a mock Neo4jClient so no real database is required.
Tests verify:
- Each query method handles non-empty and empty responses correctly.
- Data is mapped to the correct dataclass fields.
- Edge cases (no flags, no community, no conflict) return sensible defaults.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from agenteperry.graph.neo4j_queries import (
    CarouselResult,
    CommunityResult,
    CompanyFlagsResult,
    ConflictPath,
    HighRiskSupplier,
    InvestigativeQueries,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_queries(read_returns: list[dict]) -> InvestigativeQueries:
    """Build InvestigativeQueries backed by a mock client."""
    client = MagicMock()
    client.execute_read.return_value = read_returns
    return InvestigativeQueries(client=client)


# ---------------------------------------------------------------------------
# find_flags_for_company
# ---------------------------------------------------------------------------


def test_find_flags_returns_none_if_no_rows() -> None:
    q = _make_queries([])
    result = q.find_flags_for_company("20605681281")
    assert result is None


def test_find_flags_returns_company_result_with_flags() -> None:
    q = _make_queries([
        {
            "ruc": "20605681281",
            "company_name": "EMPRESA DEMO SAC",
            "flags": [
                {
                    "flag_id": "flag-1",
                    "flag_code": "OVER_SPECIFIED_EXPERIENCE",
                    "severity": "HIGH",
                    "evidence_quote": "Se requiere 5 años de experiencia especifica.",
                    "page_number": 12,
                    "ocid": "ocds-demo-001:A-1",
                    "contract_amount": 250000.0,
                },
                {
                    "flag_id": "flag-2",
                    "flag_code": "SINGLE_PROVIDER_SPEC",
                    "severity": "MEDIUM",
                    "evidence_quote": "Proveedor especifico requerido.",
                    "page_number": 7,
                    "ocid": "ocds-demo-001:A-1",
                    "contract_amount": 250000.0,
                },
            ],
        }
    ])

    result = q.find_flags_for_company("20605681281")

    assert result is not None
    assert isinstance(result, CompanyFlagsResult)
    assert result.ruc == "20605681281"
    assert result.company_name == "EMPRESA DEMO SAC"
    assert result.flag_count == 2
    assert result.high_count == 1
    assert result.flags[0].flag_code == "OVER_SPECIFIED_EXPERIENCE"
    assert result.flags[0].severity == "HIGH"
    assert result.flags[0].evidence_quote == "Se requiere 5 años de experiencia especifica."
    assert result.flags[0].page_number == 12
    assert result.flags[0].contract_amount == 250000.0


def test_find_flags_skips_entries_without_flag_id() -> None:
    q = _make_queries([
        {
            "ruc": "20605681281",
            "company_name": "EMPRESA DEMO SAC",
            "flags": [
                {"flag_id": None, "flag_code": "X", "severity": "LOW"},
                {"flag_id": "flag-1", "flag_code": "Y", "severity": "HIGH",
                 "evidence_quote": None, "page_number": None, "ocid": None, "contract_amount": None},
            ],
        }
    ])

    result = q.find_flags_for_company("20605681281")
    assert result is not None
    assert result.flag_count == 1  # None flag_id is filtered out


def test_find_flags_empty_flags_list() -> None:
    q = _make_queries([{"ruc": "20111", "company_name": "X SAC", "flags": []}])
    result = q.find_flags_for_company("20111")
    assert result is not None
    assert result.flag_count == 0
    assert result.high_count == 0


# ---------------------------------------------------------------------------
# get_high_risk_suppliers
# ---------------------------------------------------------------------------


def test_get_high_risk_suppliers_maps_rows() -> None:
    q = _make_queries([
        {
            "ruc": "20111",
            "name": "RIESGOSA SAC",
            "flag_count": 3,
            "flag_codes": ["FLAG_A", "FLAG_B", "FLAG_C"],
            "contract_count": 5,
            "total_amount": 1_000_000.0,
        }
    ])

    result = q.get_high_risk_suppliers(min_flags=2)

    assert len(result) == 1
    s = result[0]
    assert isinstance(s, HighRiskSupplier)
    assert s.ruc == "20111"
    assert s.name == "RIESGOSA SAC"
    assert s.flag_count == 3
    assert s.flag_codes == ["FLAG_A", "FLAG_B", "FLAG_C"]
    assert s.contract_count == 5
    assert s.total_amount == 1_000_000.0


def test_get_high_risk_suppliers_returns_empty_list_if_no_rows() -> None:
    q = _make_queries([])
    result = q.get_high_risk_suppliers()
    assert result == []


# ---------------------------------------------------------------------------
# find_community_around_company
# ---------------------------------------------------------------------------


def test_community_returns_zero_size_if_no_rows() -> None:
    q = _make_queries([])
    result = q.find_community_around_company("20111")
    assert isinstance(result, CommunityResult)
    assert result.community_size == 0
    assert result.community_companies == []
    assert result.person_ids == []


def test_community_maps_result() -> None:
    q = _make_queries([
        {
            "ruc": "20111",
            "company_name": "EMPRESA A SAC",
            "community_size": 3,
            "community_companies": [
                {"ruc": "20222", "name": "EMPRESA B SAC"},
                {"ruc": "20333", "name": "EMPRESA C SAC"},
                {"ruc": "20444", "name": "EMPRESA D SAC"},
            ],
            "shared_persons": ["JUAN PEREZ", "MARIA LOPEZ"],
            "person_ids": ["person_abc123", "person_def456"],
        }
    ])

    result = q.find_community_around_company("20111")

    assert result.community_size == 3
    assert len(result.community_companies) == 3
    assert result.community_companies[0]["ruc"] == "20222"
    assert "JUAN PEREZ" in result.shared_persons
    # person_ids now available for carousel detection
    assert "person_abc123" in result.person_ids
    assert len(result.person_ids) == 2


# ---------------------------------------------------------------------------
# detect_carousel
# ---------------------------------------------------------------------------


def test_carousel_returns_empty_list_if_no_rows() -> None:
    q = _make_queries([])
    result = q.detect_carousel("person_abc123")
    assert result == []


def test_carousel_maps_result() -> None:
    q = _make_queries([
        {
            "person_id": "person_abc",
            "person_name": "CARLOS GOMEZ",
            "buyer_ruc": "20131370645",
            "buyer_name": "MINSA",
            "company_count": 2,
            "companies": [
                {"ruc": "20111", "name": "EMPRESA A"},
                {"ruc": "20222", "name": "EMPRESA B"},
            ],
            "contract_count": 4,
            "total_amount": 500_000.0,
        }
    ])

    result = q.detect_carousel("person_abc")

    assert len(result) == 1
    c = result[0]
    assert isinstance(c, CarouselResult)
    assert c.person_name == "CARLOS GOMEZ"
    assert c.company_count == 2
    assert c.total_amount == 500_000.0


# ---------------------------------------------------------------------------
# find_conflict_of_interest
# ---------------------------------------------------------------------------


def test_conflict_returns_empty_list_if_no_paths() -> None:
    q = _make_queries([])
    result = q.find_conflict_of_interest("20111", "20131370645")
    assert result == []


def test_conflict_maps_paths() -> None:
    q = _make_queries([
        {
            "path_nodes": [
                {"type": "Company", "ruc": "20111", "name": "EMPRESA A"},
                {"type": "Person", "id": "p123", "name": "JUAN PEREZ"},
                {"type": "PublicEntity", "ruc": "20131370645", "name": "MINSA"},
            ],
            "path_length": 2,
        }
    ])

    result = q.find_conflict_of_interest("20111", "20131370645")

    assert len(result) == 1
    p = result[0]
    assert isinstance(p, ConflictPath)
    assert p.path_length == 2
    assert len(p.path_nodes) == 3
    assert p.path_nodes[0]["type"] == "Company"


# ---------------------------------------------------------------------------
# get_node_counts
# ---------------------------------------------------------------------------


def test_get_node_counts_returns_label_counts() -> None:
    q = _make_queries([
        {"label": "Company", "count": 1000},
        {"label": "Contract", "count": 500},
        {"label": "Flag", "count": 42},
    ])

    counts = q.get_node_counts()

    assert counts == {"Company": 1000, "Contract": 500, "Flag": 42}


def test_get_node_counts_empty_graph() -> None:
    q = _make_queries([])
    counts = q.get_node_counts()
    assert counts == {}


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


def test_context_manager_closes_own_client() -> None:
    client = MagicMock()
    q = InvestigativeQueries(client=client)
    q._own_client = True  # force close

    with q:
        pass

    client.close.assert_called_once()
