"""Change Data Capture for SEACE/OCDS contracts.

Exports:
    ChangeEvent         — a detected new or modified contract
    SEACEChangeDetector — hash-based change detection over OCDS records
    CDCPipeline         — full pipeline: detect → download → verify → dossier
    CDCStats            — run statistics
"""

from agenteperry.cdc.detector import ChangeEvent, SEACEChangeDetector
from agenteperry.cdc.pipeline import CDCPipeline, CDCStats

__all__ = [
    "ChangeEvent",
    "CDCPipeline",
    "CDCStats",
    "SEACEChangeDetector",
]
