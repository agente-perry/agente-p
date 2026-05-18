"""Collectors module."""

from agenteperry.collectors.base import (
    BaseCollector,
    BulkDownloadCollector,
    CKANCollector,
    CollectionResult,
    FormScrapingCollector,
    PlaywrightCollector,
)
from agenteperry.collectors.ckan import MefCkanCollector
from agenteperry.collectors.factory import build_collector
from agenteperry.collectors.ocds import OCDSPeruCollector
from agenteperry.collectors.oece_collector import OeceCategory, OeceCollector
from agenteperry.collectors.sunat import SunatPadronCollector

__all__ = [
    "BaseCollector",
    "BulkDownloadCollector",
    "CKANCollector",
    "CollectionResult",
    "FormScrapingCollector",
    "MefCkanCollector",
    "OeceCategory",
    "OeceCollector",
    "OCDSPeruCollector",
    "PlaywrightCollector",
    "SunatPadronCollector",
    "build_collector",
]
