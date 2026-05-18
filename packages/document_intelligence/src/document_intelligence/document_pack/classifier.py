"""Heuristic PDF classifier — assigns :class:`DocumentType` without LLM.

Classification strategy (priority order):
  1. **Filename matching** — fastest; catches obvious filenames like
     ``bases_integradas.pdf``, ``buena_pro.pdf``, ``tdr.pdf``.
  2. **Page-text probing** — read raw first 3 pages of each PDF and match
     against a keyword catalogue.  Only attempted when the file has extractable
     text to avoid forcing OCR.
  3. **Keyword scoring** — accumulate weighted hits; highest score wins.

Conflict resolution:
  ``bases_integradas`` > ``bases`` > ``tdr``  (basesIntegrated trumps plain bases)
  ``buena_pro`` > ``adjudicacion``
  ``contrato`` stands alone
  ``anexo`` is a modifier and only wins alone or with bases/TDR
  ``absolucion_consultas`` can coexist with bases
  ``unknown`` is the fallback
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from document_intelligence.document_pack.schemas import DocumentType
from document_intelligence.parsing import PDFParseError, parse_pdf

# ----------------------------------------------------------------------
# Keyword catalogue
# ----------------------------------------------------------------------
_FILENAME_SIGNALS: dict[DocumentType, list[re.Pattern[str]]] = {
    DocumentType.BASES_INTEGRADAS: [
        re.compile(r"bases[\s_]integradas", re.IGNORECASE),
        re.compile(r"bases_integradas", re.IGNORECASE),
    ],
    DocumentType.TDR: [
        re.compile(r"(?<![a-zA-Z0-9])tdr(?![a-zA-Z0-9])", re.IGNORECASE),
        re.compile(r"terminos?\s*de\s*referencia", re.IGNORECASE),
    ],
    DocumentType.BASES: [
        re.compile(r"(?<![a-zA-Z0-9])bases(?:[\s._\-]|$)", re.IGNORECASE),
        re.compile(r"bases[\s_]del[\s_]proceso", re.IGNORECASE),
    ],
    DocumentType.ABSOLUCION_CONSULTAS: [
        re.compile(r"absolu(?:cion|vemento)\s+consultas", re.IGNORECASE),
        re.compile(r"consultas?\s+y\s+absolu", re.IGNORECASE),
    ],
    DocumentType.BUENA_PRO: [
        re.compile(r"buena[\s_]pro", re.IGNORECASE),
    ],
    DocumentType.ADJUDICACION: [
        re.compile(r"(?<![a-zA-Z0-9])adjudicaci(?:on|ón)(?![a-zA-Z0-9])", re.IGNORECASE),
    ],
    DocumentType.CONTRATO: [
        re.compile(r"(?<![a-zA-Z0-9])contrato(?![a-zA-Z0-9])", re.IGNORECASE),
    ],
    DocumentType.ANEXO: [
        re.compile(r"(?<![a-zA-Z0-9])anexo(?![a-zA-Z0-9])", re.IGNORECASE),
        re.compile(r"anexos?", re.IGNORECASE),
    ],
}

_TEXT_SIGNALS: dict[DocumentType, list[tuple[str, float]]] = {
    DocumentType.BASES_INTEGRADAS: [
        ("bases integradas", 4.0),
        ("bases del proceso", 2.0),
        ("presentacion de propuestas", 1.5),
        ("calificacion y evaluacion", 1.5),
    ],
    DocumentType.TDR: [
        ("terminos de referencia", 4.0),
        ("objeto de la consultoria", 3.0),
        ("alcance del servicio", 2.0),
        ("entregables", 1.5),
    ],
    DocumentType.BASES: [
        ("bases del proceso", 3.0),
        ("convocatoria", 2.0),
        ("requisitos para participar", 2.0),
    ],
    DocumentType.ABSOLUCION_CONSULTAS: [
        ("absolucion de consultas", 4.0),
        ("respuesta a consultas", 3.0),
        ("consulta numero", 2.5),
    ],
    DocumentType.BUENA_PRO: [
        ("buena pro", 4.0),
        ("resultado de la buena pro", 3.0),
    ],
    DocumentType.ADJUDICACION: [
        ("adjudicacion", 3.0),
        ("proveedor adjudicado", 2.5),
    ],
    DocumentType.CONTRATO: [
        ("contrato de ejecucion", 3.0),
        ("firma del contrato", 2.5),
        ("clausulas del contrato", 2.0),
    ],
    DocumentType.ANEXO: [
        ("anexo", 2.0),
        ("anexos del proceso", 1.5),
    ],
}

# Higher priority value = stronger signal; tie-break by DocumentType ordering
_TYPE_PRIORITY: dict[DocumentType, int] = {
    DocumentType.BASES_INTEGRADAS: 100,
    DocumentType.TDR: 90,
    DocumentType.BASES: 80,
    DocumentType.ABSOLUCION_CONSULTAS: 70,
    DocumentType.BUENA_PRO: 60,
    DocumentType.ADJUDICACION: 50,
    DocumentType.CONTRATO: 40,
    DocumentType.ANEXO: 10,
    DocumentType.UNKNOWN: 0,
}


def _unaccent(text: str) -> str:
    replacements = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u",
        "ñ": "n", "Á": "a", "É": "e", "Í": "i", "Ó": "o", "Ú": "u", "Ü": "u", "Ñ": "n",
    }
    for acc, plain in replacements.items():
        text = text.replace(acc, plain)
    text = text.replace("—", " ").replace("–", " ").replace("-", " ")
    return text


def _score_text(text: str) -> dict[DocumentType, float]:
    scores: dict[DocumentType, float] = dict.fromkeys(DocumentType, 0.0)
    sample = _unaccent(text[:3000]).lower()
    for dtype, keywords in _TEXT_SIGNALS.items():
        for kw, weight in keywords:
            if _unaccent(kw.lower()) in sample:
                scores[dtype] += weight
    return scores


def _score_filename(name: str) -> dict[DocumentType, float]:
    scores: dict[DocumentType, float] = dict.fromkeys(DocumentType, 0.0)
    for dtype, patterns in _FILENAME_SIGNALS.items():
        for pat in patterns:
            if pat.search(name):
                scores[dtype] += 1.0
    return scores


def _merge_scores(
    fname_scores: dict[DocumentType, float],
    text_scores: dict[DocumentType, float],
) -> tuple[DocumentType, dict[str, Any]]:
    combined: dict[DocumentType, float] = dict.fromkeys(DocumentType, 0.0)
    for dtype in DocumentType:
        combined[dtype] = fname_scores[dtype] * 2.0 + text_scores[dtype]

    signals: dict[str, Any] = {
        "filename_signals": {t.value: round(s, 2) for t, s in fname_scores.items() if s > 0},
        "text_signals": {t.value: round(s, 2) for t, s in text_scores.items() if s > 0},
    }

    winner = max(combined, key=lambda t: (combined[t], _TYPE_PRIORITY[t]))
    if combined[winner] == 0.0:
        return DocumentType.UNKNOWN, signals
    return winner, signals


def _probe_text(pdf_path: Path, max_pages: int = 3) -> str:
    try:
        _, pages = parse_pdf(pdf_path)
        snippets = [p.text for p in pages[:max_pages] if p.text]
        return " ".join(snippets)
    except PDFParseError:
        return ""


def classify_document(pdf_path: Path) -> tuple[DocumentType, dict[str, Any]]:
    """Classify a PDF using filename patterns and a short text probe.

    Parameters
    ----------
    pdf_path:
        Absolute or resolved path to the PDF to classify.

    Returns
    -------
    tuple[DocumentType, dict[str, Any]]
        The resolved type and a ``classification_signals`` blob for audit.
    """
    name = pdf_path.name

    fname_scores = _score_filename(name)
    text = _probe_text(pdf_path)
    text_scores = _score_text(text) if text else dict.fromkeys(DocumentType, 0.0)

    dtype, signals = _merge_scores(fname_scores, text_scores)
    signals["text_probed_pages"] = min(3, len(text) // 500) if text else 0
    return dtype, signals