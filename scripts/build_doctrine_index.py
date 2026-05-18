#!/usr/bin/env python3
"""Build the DoctrineIndex artifact from real public PDFs (PR #12).

Inputs (defaults):
    data/PDF-Base/OCP2024-RedFlagProcurement-1.pdf
    data/PDF-Base/795de142-en.pdf                  (OECD Governing with AI)

Outputs:
    data/doctrine/manifest.json
    data/doctrine/chunks.jsonl
    data/doctrine/vectors.npy
    data/doctrine/processed/<source>.txt           (debug)

Each chunk carries:
    chunk_id, source_document, source_url, page_number, section_title,
    text, quote, flag_codes, metadata.

The builder reuses the existing `flags/doctrine_mapping.yaml` to decide
which flag codes each chunk supports. Chunks that match no flag are kept
but with `flag_codes=[]` — they remain searchable as background corpus.

Usage:
    python scripts/build_doctrine_index.py
    python scripts/build_doctrine_index.py --rebuild --embed mock
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "packages" / "document_intelligence" / "src"))

import numpy as np  # noqa: E402 — must come after sys.path insertion
import yaml  # type: ignore[import-untyped]  # noqa: E402


@dataclass(frozen=True)
class SourceSpec:
    """One PDF to ingest."""

    source_document: str
    source_url: str
    file_path: Path
    authority_type: str
    country_scope: str
    language: str


def _default_sources() -> list[SourceSpec]:
    return [
        SourceSpec(
            source_document="OCP Red Flags in Public Procurement (2024)",
            source_url="https://www.open-contracting.org/resources/red-flags-in-public-procurement/",
            file_path=REPO_ROOT / "data" / "PDF-Base" / "OCP2024-RedFlagProcurement-1.pdf",
            authority_type="procurement_red_flags",
            country_scope="international",
            language="en",
        ),
        SourceSpec(
            source_document="OECD Governing with Artificial Intelligence (2024)",
            source_url="https://www.oecd.org/governance/governing-with-artificial-intelligence/",
            file_path=REPO_ROOT / "data" / "PDF-Base" / "795de142-en.pdf",
            authority_type="ai_governance",
            country_scope="international",
            language="en",
        ),
    ]


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


_FLAG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "EXCESSIVE_DOCUMENT_REQUIREMENT": (
        "excessive documentation",
        "documentary requirements",
        "documentary burden",
        "notari",
        "legaliz",
        "physical document",
        "lengthy paperwork",
        "burdensome documentation",
        "administrative burden",
        # OCP-specific phrasing for paperwork burden (avoid "prequalification"
        # which collides with OVER_SPECIFIED_EXPERIENCE — keep that one only
        # under the OVER flag).
        "compliance with paperwork",
    ),
    "OBSOLETE_PHYSICAL_FORMAT": (
        "physical format",
        "printed copies",
        "paper-based",
        "hard copy",
        "in person submission",
    ),
    "OVER_SPECIFIED_EXPERIENCE": (
        "over-specified experience",
        "narrow experience",
        "tailored experience",
        "tailored to a specific",
        "restrictive qualification",
        "qualification criteria",
        "narrow qualification",
        "specific bidder",
        "tailoring requirements",
        "unreasonable prequalification",
        "restrictive prequalification",
        "prequalification requirements",
        "technical specifications are too",
        "specifications too narrow",
        "favor a specific",
        "prequalification criteria",
    ),
    "SPECIFIC_EQUIPMENT_REQUIREMENT": (
        "brand name specification",
        "specific brand",
        "or equivalent",
        "particular brand",
        "single source",
        "sole source",
        "specifications are too broad or too narrow",
        "technical specifications too narrow",
        "specifications favor",
        "tailored to a specific bidder",
        "trademark",
    ),
    "EXCESSIVE_CERTIFICATION_REQUIREMENT": (
        "excessive certification",
        "iso certification",
        "certification requirement",
        "accreditation requirement",
    ),
    "SUBJECTIVE_EVALUATION_CRITERIA": (
        "subjective criteria",
        "discretion",
        "discretionary",
        "without measurable",
        "without clear criteria",
        "evaluator's judgment",
        "without weighted criteria",
    ),
    "UNREALISTIC_DEADLINE": (
        "short deadline",
        "tight deadline",
        "insufficient time",
        "unreasonable timeline",
        "rushed timeline",
        "abnormally short",
    ),
    "LOW_TRACEABILITY_OUTPUT": (
        "traceability",
        "audit trail",
        "machine readable",
        "structured data",
        "open data",
        "dataset deliverable",
        "non-structured",
    ),
    "AI_NO_AUDIT_TRAIL": (
        "ai accountability",
        "automated decision",
        "algorithmic",
        "ai governance",
        "human oversight",
        "audit trail",
    ),
}


def _assign_flags(text: str) -> list[str]:
    haystack = _normalize(text)
    matched: list[str] = []
    for flag_code, keywords in _FLAG_KEYWORDS.items():
        for keyword in keywords:
            if keyword in haystack:
                matched.append(flag_code)
                break
    return matched


def _detect_section(page_text: str, previous: str) -> str:
    """Heuristic section detection — looks for Title Case headings."""
    for line in page_text.splitlines()[:8]:
        stripped = line.strip()
        if not stripped or len(stripped) > 90:
            continue
        if stripped.endswith("."):
            continue
        words = stripped.split()
        if len(words) < 2 or len(words) > 12:
            continue
        title_case = sum(
            1 for w in words if w and (w[0].isupper() or w in {"and", "of", "in", "to", "the", "for"})
        )
        if title_case >= max(2, len(words) - 1):
            return stripped
    return previous


def _make_chunk_id(source: str, page: int, idx: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", source.lower()).strip("_")[:32]
    return f"{slug}_p{page:03d}_{idx:03d}"


def _chunk_text(text: str, *, target_chars: int = 700, min_chars: int = 200) -> list[str]:
    """Paragraph-aware chunker with target ~700 chars."""
    if len(text) <= target_chars:
        return [text] if text.strip() else []
    parts: list[str] = []
    buf: list[str] = []
    buf_len = 0
    for paragraph in re.split(r"\n\s*\n", text):
        para = paragraph.strip()
        if not para:
            continue
        if buf_len + len(para) > target_chars and buf_len >= min_chars:
            parts.append("\n\n".join(buf).strip())
            buf = [para]
            buf_len = len(para)
        else:
            buf.append(para)
            buf_len += len(para) + 2
    if buf:
        parts.append("\n\n".join(buf).strip())
    return [p for p in parts if p]


def _ingest_pdf(spec: SourceSpec, processed_dir: Path) -> list[dict[str, Any]]:
    """Parse one PDF into doctrine chunks. Returns list of chunk dicts."""
    if not spec.file_path.exists():
        print(f"  WARN missing source: {spec.file_path}", file=sys.stderr)
        return []
    import fitz  # PyMuPDF

    chunks: list[dict[str, Any]] = []
    section_title = ""
    processed_lines: list[str] = []
    with fitz.open(spec.file_path) as doc:  # type: ignore[no-untyped-call]
        for page_idx in range(len(doc)):
            page_text_raw: str = str(doc.load_page(page_idx).get_text("text") or "")
            page_text = re.sub(r"[ \t]+", " ", page_text_raw).strip()
            if not page_text:
                continue
            section_title = _detect_section(page_text, section_title)
            processed_lines.append(f"=== p{page_idx + 1} | {section_title} ===")
            processed_lines.append(page_text)
            for sub_idx, fragment in enumerate(_chunk_text(page_text)):
                flag_codes = _assign_flags(fragment)
                chunk_id = _make_chunk_id(spec.source_document, page_idx + 1, sub_idx)
                quote = fragment[:480].strip()
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "source_document": spec.source_document,
                        "source_url": spec.source_url,
                        "page_number": page_idx + 1,
                        "section_title": section_title or None,
                        "text": fragment,
                        "quote": quote,
                        "flag_codes": flag_codes,
                        "metadata": {
                            "authority_type": spec.authority_type,
                            "country_scope": spec.country_scope,
                            "language": spec.language,
                        },
                    }
                )

    processed_path = processed_dir / f"{spec.file_path.stem}.txt"
    processed_path.write_text("\n".join(processed_lines), encoding="utf-8")
    return chunks


def _to_doctrine_chunk_dict(c: dict[str, Any]) -> dict[str, Any]:
    """Project the rich builder chunk into the DoctrineChunk schema expected by the loader.

    The loader's ``DoctrineChunk`` schema accepts: chunk_id, source, section, page, text, flag_code.
    Extra fields are stripped here so ``extra="forbid"`` does not reject the payload.
    """
    flag_codes = c["flag_codes"]
    flag_code = flag_codes[0] if flag_codes else None
    return {
        "chunk_id": c["chunk_id"],
        "source": c["source_document"],
        "section": c.get("section_title"),
        "page": c["page_number"],
        "text": c["text"],
        "flag_code": flag_code,
    }


def _embed(chunks: list[dict[str, Any]], *, mode: str = "mock", dim: int = 256) -> np.ndarray:
    from document_intelligence.embeddings import get_embedder

    embedder = get_embedder(mode, dim=dim)
    texts = [c["text"] for c in chunks]
    return embedder.embed(texts) if texts else np.zeros((0, dim), dtype=np.float32)


def _checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def build_doctrine(
    sources: list[SourceSpec] | None = None,
    *,
    out_dir: Path | None = None,
    embed_mode: str = "mock",
    embed_dim: int = 256,
) -> dict[str, Any]:
    """Build manifest + chunks.jsonl + vectors.npy."""
    sources = sources or _default_sources()
    out_dir = out_dir or (REPO_ROOT / "data" / "doctrine")
    processed_dir = out_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    all_chunks: list[dict[str, Any]] = []
    for spec in sources:
        print(f"ingesting: {spec.source_document}")
        chunks = _ingest_pdf(spec, processed_dir)
        print(f"  {len(chunks)} chunks")
        all_chunks.extend(chunks)

    # Per-flag counts for the manifest.
    flag_counts: dict[str, int] = {}
    for c in all_chunks:
        for code in c["flag_codes"]:
            flag_counts[code] = flag_counts.get(code, 0) + 1

    # Loader-compatible jsonl (strips extras).
    chunks_path = out_dir / "chunks.jsonl"
    rich_path = out_dir / "chunks.rich.jsonl"
    with chunks_path.open("w", encoding="utf-8") as handle:
        for c in all_chunks:
            handle.write(json.dumps(_to_doctrine_chunk_dict(c), ensure_ascii=False))
            handle.write("\n")
    with rich_path.open("w", encoding="utf-8") as handle:
        for c in all_chunks:
            handle.write(json.dumps(c, ensure_ascii=False))
            handle.write("\n")

    vectors = _embed(all_chunks, mode=embed_mode, dim=embed_dim)
    vectors_path = out_dir / "vectors.npy"
    np.save(vectors_path, vectors)

    manifest = {
        "version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "embed_mode": embed_mode,
        "dim": int(vectors.shape[1]) if vectors.size else embed_dim,
        "count": len(all_chunks),
        "chunks_file": "chunks.jsonl",
        "rich_chunks_file": "chunks.rich.jsonl",
        "vectors_file": "vectors.npy",
        "sources": [
            {
                "source_document": s.source_document,
                "source_url": s.source_url,
                "file_name": s.file_path.name,
                "checksum": (
                    _checksum(s.file_path.read_bytes()) if s.file_path.exists() else None
                ),
                "authority_type": s.authority_type,
                "country_scope": s.country_scope,
                "language": s.language,
            }
            for s in sources
        ],
        "flag_chunk_counts": flag_counts,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # Update doctrine_mapping.yaml with a digest of what was indexed.
    mapping_path = (
        REPO_ROOT
        / "packages"
        / "document_intelligence"
        / "src"
        / "document_intelligence"
        / "flags"
        / "doctrine_mapping.yaml"
    )
    if mapping_path.parent.exists():
        mapping_out: dict[str, Any] = {}
        for flag_code, count in sorted(flag_counts.items()):
            samples = [c for c in all_chunks if flag_code in c["flag_codes"]][:3]
            mapping_out[flag_code] = {
                "doctrine_chunk_count": count,
                "doctrine_status": "real" if count > 0 else "stub",
                "doctrine_sources": [
                    {
                        "source_document": s["source_document"],
                        "source_url": s["source_url"],
                        "page_number": s["page_number"],
                        "section_title": s.get("section_title"),
                        "quote": s["quote"][:200],
                    }
                    for s in samples
                ],
            }
        mapping_path.write_text(
            yaml.safe_dump(mapping_out, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--embed", choices=("mock", "local-embed", "llm"), default="mock")
    parser.add_argument("--dim", type=int, default=256)
    args = parser.parse_args()
    manifest = build_doctrine(out_dir=args.out, embed_mode=args.embed, embed_dim=args.dim)
    print(f"wrote {manifest['count']} chunks → {args.out or REPO_ROOT / 'data' / 'doctrine'}")
    print(f"per-flag counts: {manifest['flag_chunk_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
