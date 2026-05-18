"""Safety filters: legal-safe gate for final output."""

from __future__ import annotations

from document_intelligence.safety.legal_filter import BannedTermFoundError, LegalSafetyFilter

__all__ = ["BannedTermFoundError", "LegalSafetyFilter"]