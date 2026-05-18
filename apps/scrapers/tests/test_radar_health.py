from __future__ import annotations

from agenteperry.radar import health


def test_check_source_health_existing_source(monkeypatch) -> None:
    monkeypatch.setattr(health, "_light_url_check", lambda url, enabled: True)

    result = health.check_source_health("ocds_peru")

    assert result.source_code == "ocds_peru"
    assert result.status in {"ok", "degraded", "unknown"}
    assert result.details["collector_available"] is True


def test_check_source_health_unknown_source() -> None:
    result = health.check_source_health("missing_source")

    assert result.status == "failed"
    assert result.error


def test_check_all_sources_does_not_raise(monkeypatch) -> None:
    monkeypatch.setattr(health, "_light_url_check", lambda url, enabled: None)

    results = health.check_all_sources()

    assert results
    assert any(result.source_code == "ocds_peru" for result in results)
