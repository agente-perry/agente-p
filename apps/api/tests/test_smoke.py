"""Smoke tests — exercise routers without hitting GCS or Neo4j."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from agenteperry_api.main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_health_returns_ok() -> None:
    client = _client()
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "api_version" in body
    assert "gcs_bucket" in body
    assert "neo4j_enabled" in body
    assert "auditor_available" in body


def test_graph_endpoint_returns_503_when_neo4j_disabled() -> None:
    client = _client()
    with patch(
        "agenteperry_api.services.neo4j_reader.is_enabled", return_value=False
    ):
        res = client.get("/graph/counts")
        assert res.status_code == 503


def test_dossiers_list_calls_gcs() -> None:
    """When GCS is mocked, the dossiers router must shape the response correctly."""
    client = _client()
    with (
        patch(
            "agenteperry_api.services.gcs.list_directories",
            return_value=["ocds_dgv273_seacev3_988512"],
        ),
        patch(
            "agenteperry_api.services.gcs.list_blobs",
            return_value=[
                "scraped/results/ocds_dgv273_seacev3_988512/dossier.json",
                "scraped/results/ocds_dgv273_seacev3_988512/flags.json",
            ],
        ),
    ):
        res = client.get("/dossiers")
        assert res.status_code == 200
        items = res.json()
        assert isinstance(items, list)
        assert len(items) == 1
        assert items[0]["has_dossier_json"] is True
        assert items[0]["has_flags_json"] is True
        assert items[0]["has_pages_json"] is False


def test_dossier_get_returns_payload_when_present() -> None:
    client = _client()
    fake_payload = {"schema_version": "1.0", "risk_summary": {"total_score": 60}}
    with patch("agenteperry_api.services.gcs.read_json", return_value=fake_payload):
        res = client.get("/dossiers/ocds-dgv273-seacev3-988512")
        assert res.status_code == 200
        assert res.json() == fake_payload


def test_dossier_get_404_when_missing() -> None:
    client = _client()
    with patch("agenteperry_api.services.gcs.read_json", return_value=None):
        res = client.get("/dossiers/ocds-x")
        assert res.status_code == 404


def test_demo_cases_hydrates_from_gcs() -> None:
    client = _client()
    fake_dossier = {
        "risk_summary": {"risk_level": "ALTO", "total_score": 60, "total_flags": 6},
        "flags": [
            {
                "severity": "LOW",
                "evidence_quote": "lorem",
                "page_number": 12,
            }
        ],
    }
    with patch("agenteperry_api.services.gcs.read_json", return_value=fake_dossier):
        res = client.get("/demo/cases")
        assert res.status_code == 200
        cases = res.json()
        assert len(cases) >= 1
        assert cases[0]["risk_level"] == "ALTO"
        assert cases[0]["score"] == 60


def test_audit_returns_501_when_auditor_unavailable() -> None:
    client = _client()
    with patch(
        "agenteperry_api.services.auditor.is_available", return_value=False
    ):
        res = client.post("/audit/ocds-x", json={})
        assert res.status_code == 501
