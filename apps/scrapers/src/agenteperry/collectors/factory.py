"""Collector factory for registered sources."""

from __future__ import annotations

from agenteperry.collectors.base import BaseCollector
from agenteperry.collectors.ckan import MefCkanCollector
from agenteperry.collectors.ocds import OCDSPeruCollector
from agenteperry.collectors.oece_collector import OeceCollector
from agenteperry.collectors.sanciones import SancionesCollector
from agenteperry.collectors.sunat import SunatPadronCollector
from agenteperry.sources.catalog import SourceCatalogEntry


def build_collector(source: SourceCatalogEntry) -> BaseCollector:
    """Build a concrete collector for sources implemented in SPEC-0006."""
    if source.source_code == "ocds_peru":
        return OCDSPeruCollector(source)
    if source.source_code == "sunat_padron":
        return SunatPadronCollector(source)
    if source.source_code == "seace_oece":
        return OeceCollector(source)
    if source.source_code == "contraloria_sanciones":
        return SancionesCollector(source)
    if source.source_code == "mef_datos_abiertos":
        return MefCkanCollector(source)
    raise NotImplementedError(f"Collector not implemented for source: {source.source_code}")
