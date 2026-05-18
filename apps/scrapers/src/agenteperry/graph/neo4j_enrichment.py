"""Graph enrichment for TDR dossiers — SPEC-0012.

This is the bridge between the documentary evidence pipeline (TDR → Flags)
and the investigative graph (Neo4j Aura).

``enrich_dossier_with_graph`` takes a dossier dict produced by
``tdr.dossier.generate_dossier`` and adds a ``graph_findings`` block with:

- ``flags_in_graph``    — how many of the TDR flags already exist in Neo4j
- ``carousel``          — carousel pattern detected via shared representatives
- ``community``         — business community around the winning company
- ``conflict_paths``    — Person-mediated paths to the buying entity
- ``risk_delta``        — additional risk points contributed by graph findings

Risk scoring (additive, capped at +50 extra points):

  +15  — company has >= 2 existing flags in graph
  +20  — carousel pattern found (1 person, >= 2 companies, same buyer)
  +10  — business community >= 3 related companies
  +25  — conflict-of-interest path found (supplier ↔ buyer via Person)

All findings are labelled "presenta senales de riesgo" — not accusations.
Every finding cites the evidence source (ruc, canonical_id, path nodes).

Usage (optional — requires neo4j extra)::

    from agenteperry.graph.neo4j_enrichment import enrich_dossier_with_graph

    dossier = generate_dossier(...)
    enriched = enrich_dossier_with_graph(
        dossier=dossier,
        supplier_ruc="20605681281",
        buyer_ruc="20131370645",
    )
    # enriched["graph_findings"] is now populated
"""

from __future__ import annotations

from typing import Any, cast

import structlog

from agenteperry.graph.neo4j_client import Neo4jClient
from agenteperry.graph.neo4j_queries import InvestigativeQueries

log = structlog.get_logger(__name__)

# Points added per graph pattern (capped collectively at MAX_DELTA)
_SCORE_EXISTING_FLAGS = 15
_SCORE_CAROUSEL = 20
_SCORE_COMMUNITY = 10
_SCORE_CONFLICT = 25
_MAX_DELTA = 50


def enrich_dossier_with_graph(
    *,
    dossier: dict[str, Any],
    supplier_ruc: str,
    buyer_ruc: str | None = None,
    neo4j_client: Neo4jClient | None = None,
) -> dict[str, Any]:
    """Enrich a dossier dict with graph-derived findings.

    Mutates and returns the dossier with a ``graph_findings`` key added.
    If Neo4j is unavailable or credentials are missing, returns the dossier
    unchanged with ``graph_findings = {"error": "<reason>"}``.

    Args:
        dossier:        Output of ``tdr.dossier.generate_dossier``.
        supplier_ruc:   RUC of the winning company.
        buyer_ruc:      RUC of the buying entity (optional — conflict check skipped if None).
        neo4j_client:   Inject a pre-built client (for testing / reuse).

    Returns:
        The same dossier dict with ``graph_findings`` populated.
    """
    findings: dict[str, Any] = {
        "supplier_ruc": supplier_ruc,
        "buyer_ruc": buyer_ruc,
        "flags_in_graph": 0,
        "carousel": [],
        "community": {"community_size": 0, "companies": [], "shared_persons": []},
        "conflict_paths": [],
        "risk_delta": 0,
        "signals": [],
        "error": None,
    }

    own_client = neo4j_client is None
    try:
        client = neo4j_client or Neo4jClient()
    except (ValueError, ImportError) as exc:
        findings["error"] = str(exc)
        dossier["graph_findings"] = findings
        log.warning("neo4j.enrich.skipped", reason=str(exc))
        return dossier

    try:
        with InvestigativeQueries(client=client) as q:
            delta = _run_enrichment(q, supplier_ruc, buyer_ruc, findings)
        findings["risk_delta"] = min(delta, _MAX_DELTA)
        log.info(
            "neo4j.enrichment.done",
            supplier_ruc=supplier_ruc,
            delta=findings["risk_delta"],
            signals=len(findings["signals"]),
        )
    except Exception as exc:  # noqa: BLE001
        findings["error"] = str(exc)
        log.warning("neo4j.enrich.error", error=str(exc), supplier_ruc=supplier_ruc)
    finally:
        if own_client:
            client.close()

    dossier["graph_findings"] = findings
    return dossier


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_enrichment(
    q: InvestigativeQueries,
    supplier_ruc: str,
    buyer_ruc: str | None,
    findings: dict[str, Any],
) -> int:
    """Execute all investigative queries and populate findings.  Returns delta score."""
    delta = 0

    # 1. Flags already in graph for this company
    company_flags = q.find_flags_for_company(supplier_ruc)
    if company_flags and company_flags.flag_count >= 2:
        findings["flags_in_graph"] = company_flags.flag_count
        delta += _SCORE_EXISTING_FLAGS
        findings["signals"].append({
            "type": "HISTORIAL_SENALES",
            "description": (
                f"{company_flags.company_name} presenta "
                f"{company_flags.flag_count} senales de riesgo documentadas en el historial "
                f"({company_flags.high_count} de severidad alta)."
            ),
            "score_contribution": _SCORE_EXISTING_FLAGS,
            "evidence": [
                {
                    "flag_code": f.flag_code,
                    "severity": f.severity,
                    "page": f.page_number,
                    "ocid": f.ocid,
                }
                for f in company_flags.flags[:5]
            ],
        })

    # 2. Community (shared representatives)
    community = q.find_community_around_company(supplier_ruc)
    if community.community_size >= 3:
        findings["community"] = {
            "community_size": community.community_size,
            "companies": community.community_companies[:10],
            "shared_persons": community.shared_persons[:5],
        }
        delta += _SCORE_COMMUNITY
        findings["signals"].append({
            "type": "RED_EMPRESARIAL",
            "description": (
                f"La empresa pertenece a una red de {community.community_size} empresas "
                f"controladas por los mismos representantes "
                f"({', '.join(community.shared_persons[:2])})."
            ),
            "score_contribution": _SCORE_COMMUNITY,
            "evidence": community.community_companies[:5],
        })

    # 3. Carousel — iterate known person canonical_ids from community query
    #    (person_ids is now returned by _Q_COMMUNITY via collect(DISTINCT p.canonical_id))
    for person_id in community.person_ids[:3]:
        carousels = q.detect_carousel(person_id)
        if not carousels:
            continue
        # Take the most significant match (ordered by company_count DESC in Cypher)
        top = carousels[0]
        findings["carousel"].append({
            "person_id": top.person_id,
            "person_name": top.person_name,
            "buyer_ruc": top.buyer_ruc,
            "buyer_name": top.buyer_name,
            "company_count": top.company_count,
            "companies": top.companies[:10],
            "contract_count": top.contract_count,
            "total_amount": top.total_amount,
        })
        delta += _SCORE_CAROUSEL
        findings["signals"].append({
            "type": "CARRUSEL_EMPRESARIAL",
            "description": (
                f"{top.person_name} controla {top.company_count} empresas que ganaron "
                f"contratos con {top.buyer_name}. "
                f"Patron tipico de carrusel: multiples empresas bajo un mismo controlador "
                f"compiten (o no compiten) en la misma entidad."
            ),
            "score_contribution": _SCORE_CAROUSEL,
            "evidence": top.companies[:5],
        })
        break  # one carousel signal per company is enough

    # 4. Conflict of interest paths (requires buyer_ruc)
    if buyer_ruc:
        paths = q.find_conflict_of_interest(supplier_ruc, buyer_ruc)
        if paths:
            findings["conflict_paths"] = [
                {
                    "path_length": p.path_length,
                    "path_nodes": p.path_nodes,
                }
                for p in paths[:3]
            ]
            delta += _SCORE_CONFLICT
            shortest = paths[0]
            findings["signals"].append({
                "type": "POSIBLE_CONFLICTO_INTERES",
                "description": (
                    f"Se detectó un camino de {shortest.path_length} nodos entre el proveedor "
                    f"y la entidad compradora a través de personas vinculadas. "
                    f"Esta conexión merece revisión."
                ),
                "score_contribution": _SCORE_CONFLICT,
                "evidence": shortest.path_nodes,
            })

    return delta


def render_graph_findings_markdown(findings: dict[str, Any]) -> str:
    """Render graph findings as a Markdown section for inclusion in dossier.

    Returns an empty string if there are no findings or if graph was unavailable.
    """
    if findings.get("error") or not findings.get("signals"):
        return ""

    lines: list[str] = [
        "",
        "---",
        "",
        "## Hallazgos del Grafo Investigativo",
        "",
        "> *Estas señales provienen del análisis de red empresarial. "
        "No constituyen acusación. Cada hallazgo merece revisión independiente.*",
        "",
    ]

    for i, signal in enumerate(findings.get("signals") or [], start=1):
        signal_d = cast(dict[str, Any], signal)
        lines.append(f"### {i}. {str(signal_d['type']).replace('_', ' ').title()}")
        lines.append("")
        lines.append(str(signal_d["description"]))
        lines.append("")
        evidence = cast(list[Any], signal_d.get("evidence") or [])
        if evidence and isinstance(evidence[0], dict):
            for item in evidence[:3]:
                item_d = cast(dict[str, Any], item)
                if "flag_code" in item_d:
                    lines.append(
                        f"- **{item_d['flag_code']}** (severidad: {item_d.get('severity', '?')}, "
                        f"pág. {item_d.get('page', '?')}, OCID: `{item_d.get('ocid', '?')}`)"
                    )
                elif "ruc" in item_d:
                    lines.append(f"- {item_d.get('name', '?')} (RUC: {item_d.get('ruc', '?')})")
                elif "type" in item_d:
                    lines.append(
                        f"- [{item_d['type']}] "
                        f"{item_d.get('name', item_d.get('ruc', item_d.get('id', '?')))}"
                    )
        lines.append("")

    delta = findings.get("risk_delta", 0)
    if delta:
        lines.append(f"**Puntos de riesgo adicionales por grafo: +{delta}**")
        lines.append("")

    return "\n".join(lines)
