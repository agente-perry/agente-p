"""AgentePerry FastAPI backend.

Read-only over the GCP project ``agente-perry`` (bucket
``agente-perry-data-prod``) + Neo4j AuraDB graph, with optional write-path
through ``document_intelligence`` for on-demand re-audit of a TDR.
"""

from __future__ import annotations

__version__ = "0.1.0"
