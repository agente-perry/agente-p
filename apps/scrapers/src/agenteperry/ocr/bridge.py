# pyright: reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnknownMemberType=false
"""Bridge OCR outputs into TDR-analyzer-ready bundles with provenance."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agenteperry.tdr.chunking import chunk_pages
from agenteperry.tdr.flags import detect_flags_in_pages
from agenteperry.tdr.models import TdrPage

OCID_PATTERN = re.compile(r"ocds[-_][a-z0-9]+[-_][a-z0-9]+[-_][a-z0-9_\-]+", re.IGNORECASE)


@dataclass
class BridgeResult:
    document_id: str
    ocid: str | None
    status: str
    bundle_dir: str | None
    reason: str | None = None


@dataclass
class AnalyzerPrepareResult:
    document_id: str
    ocid: str | None
    status: str
    chunks_count: int = 0
    flags_count: int = 0
    bundle_dir: str | None = None
    reason: str | None = None


@dataclass
class LoaderPrepareResult:
    document_id: str
    ocid: str | None
    status: str
    manifest_jsonl: str | None = None
    bundle_dir: str | None = None
    reason: str | None = None


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        raw = json.loads(stripped)
        if isinstance(raw, dict):
            rows.append(raw)
    return rows


def _extract_ocid_from_text(value: str) -> str | None:
    m = OCID_PATTERN.search(value.replace("_", "-"))
    return _normalize_ocid(m.group(0)) if m else None


def _normalize_ocid(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace("_", "-")
    return normalized or None


def _extract_ocid_from_manifest(manifest: dict[str, Any]) -> str | None:
    if manifest.get("ocid"):
        return _normalize_ocid(str(manifest["ocid"]))
    for field in ("document_id", "source_pdf_path"):
        value = manifest.get(field)
        if isinstance(value, str):
            found = _extract_ocid_from_text(value)
            if found:
                return found
    return None


def _build_contract_index(records_jsonl: Path) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(records_jsonl):
        ocid = _normalize_ocid(str(row.get("ocid") or row.get("external_id") or ""))
        if not ocid:
            continue
        index[ocid] = row
    return index


def _build_pages_json(ocr_pages_jsonl: Path, tdr_id: str) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    for row in _read_jsonl(ocr_pages_jsonl):
        page_number = int(row.get("page_number") or 0)
        text = str(row.get("text") or "")
        pages.append({"tdr_id": tdr_id, "page_number": page_number, "text_content": text})
    pages.sort(key=lambda item: int(item["page_number"]))
    return {"pages": pages}


def build_ocr_bridge_bundles(
    ocr_root: Path,
    output_dir: Path,
    contracts_jsonl: Path | None = None,
    limit: int | None = None,
    strict: bool = True,
) -> list[BridgeResult]:
    root = ocr_root.resolve()
    out = output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)

    contracts_index = _build_contract_index(contracts_jsonl) if contracts_jsonl else {}
    manifest_paths = sorted(root.glob("*/ocr_manifest.json"))
    if limit is not None:
        manifest_paths = manifest_paths[:limit]

    results: list[BridgeResult] = []
    for manifest_path in manifest_paths:
        manifest = _read_json(manifest_path)
        document_id = str(manifest.get("document_id") or manifest_path.parent.name)
        ocid = _extract_ocid_from_manifest(manifest)
        source_dir = manifest_path.parent
        pages_jsonl = source_dir / "ocr_pages.jsonl"
        text_path = source_dir / "ocr_text.txt"

        if not pages_jsonl.exists() or not text_path.exists():
            results.append(
                BridgeResult(
                    document_id=document_id,
                    ocid=ocid,
                    status="skipped",
                    bundle_dir=None,
                    reason="missing_ocr_outputs",
                )
            )
            continue

        contract_row = contracts_index.get(ocid or "") if ocid else None
        if contract_row is None:
            manifest_ocid = _normalize_ocid(str(manifest.get("ocid") or ""))
            contract_row = contracts_index.get(manifest_ocid or "") if manifest_ocid else None
        if strict and contracts_jsonl and contract_row is None:
            results.append(
                BridgeResult(
                    document_id=document_id,
                    ocid=ocid,
                    status="skipped",
                    bundle_dir=None,
                    reason="missing_contract_context",
                )
            )
            continue

        bundle_dir = out / document_id
        bundle_dir.mkdir(parents=True, exist_ok=True)

        pages_payload = _build_pages_json(pages_jsonl, tdr_id=document_id)
        pages_path = bundle_dir / "pages.json"
        pages_path.write_text(json.dumps(pages_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        related_artifacts: list[dict[str, Any]] = []
        if isinstance(contract_row, dict):
            for doc in contract_row.get("documents") or []:
                if not isinstance(doc, dict):
                    continue
                related_artifacts.append(
                    {
                        "title": doc.get("title"),
                        "url": doc.get("url"),
                        "format": doc.get("format"),
                        "datePublished": doc.get("datePublished"),
                    }
                )

        context_payload = {
            "document_id": document_id,
            "ocid": ocid,
            "contract_context": {
                "entity_name": (contract_row or {}).get("entity_name") if contract_row else None,
                "entity_ruc": (contract_row or {}).get("entity_ruc") if contract_row else None,
                "supplier_name": (contract_row or {}).get("supplier_name") if contract_row else None,
                "supplier_ruc": (contract_row or {}).get("supplier_ruc") if contract_row else None,
                "monto": (contract_row or {}).get("monto") if contract_row else None,
                "fecha": (contract_row or {}).get("fecha") if contract_row else None,
                "source_url": (contract_row or {}).get("source_url") if contract_row else None,
            },
            "related_artifacts": related_artifacts,
        }
        context_path = bundle_dir / "contract_context.json"
        context_path.write_text(json.dumps(context_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        provenance_payload = {
            "document_id": document_id,
            "ocid": ocid,
            "source_pdf_path": manifest.get("source_pdf_path"),
            "source_pdf_sha256": manifest.get("source_pdf_sha256"),
            "ocr_manifest_path": str(manifest_path),
            "ocr_pages_path": str(pages_jsonl),
            "ocr_text_path": str(text_path),
            "bridge_output": {
                "pages_json": str(pages_path),
                "contract_context_json": str(context_path),
            },
            "traceability": {
                "has_contract_match": bool(contract_row),
                "related_artifacts_count": len(related_artifacts),
            },
        }
        provenance_path = bundle_dir / "provenance.json"
        provenance_path.write_text(json.dumps(provenance_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        bundle_manifest = {
            "document_id": document_id,
            "ocid": ocid,
            "status": "ready",
            "inputs": {
                "ocr_manifest": str(manifest_path),
                "ocr_pages": str(pages_jsonl),
                "ocr_text": str(text_path),
            },
            "outputs": {
                "pages_json": str(pages_path),
                "contract_context_json": str(context_path),
                "provenance_json": str(provenance_path),
            },
        }
        (bundle_dir / "bundle_manifest.json").write_text(
            json.dumps(bundle_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        results.append(BridgeResult(document_id=document_id, ocid=ocid, status="ready", bundle_dir=str(bundle_dir)))

    return results


def _load_pages_from_bundle(pages_json: Path) -> list[TdrPage]:
    payload = _read_json(pages_json)
    pages_raw = payload.get("pages") or []
    pages: list[TdrPage] = []
    for row in pages_raw:
        if not isinstance(row, dict):
            continue
        pages.append(
            TdrPage(
                tdr_id=str(row.get("tdr_id") or ""),
                page_number=int(row.get("page_number") or 0),
                text_content=str(row.get("text_content") or ""),
            )
        )
    return [p for p in pages if p.page_number > 0]


def prepare_analyzer_bundles(
    bridge_root: Path,
    *,
    limit: int | None = None,
    max_chars: int = 1200,
    overlap_chars: int = 160,
    strict: bool = True,
) -> list[AnalyzerPrepareResult]:
    root = bridge_root.resolve()
    bundle_manifests = sorted(root.glob("*/bundle_manifest.json"))
    if limit is not None:
        bundle_manifests = bundle_manifests[:limit]

    results: list[AnalyzerPrepareResult] = []
    analyzer_index: list[dict[str, Any]] = []

    for manifest_path in bundle_manifests:
        bundle = _read_json(manifest_path)
        document_id = str(bundle.get("document_id") or manifest_path.parent.name)
        ocid = bundle.get("ocid") if isinstance(bundle.get("ocid"), str) else None
        out_raw = bundle.get("outputs")
        out: dict[str, Any] = out_raw if isinstance(out_raw, dict) else {}
        pages_path_raw = out.get("pages_json")
        if not isinstance(pages_path_raw, str):
            results.append(
                AnalyzerPrepareResult(
                    document_id=document_id,
                    ocid=ocid,
                    status="skipped",
                    bundle_dir=str(manifest_path.parent),
                    reason="missing_pages_json",
                )
            )
            continue

        pages_path = Path(pages_path_raw)
        if not pages_path.exists():
            results.append(
                AnalyzerPrepareResult(
                    document_id=document_id,
                    ocid=ocid,
                    status="skipped",
                    bundle_dir=str(manifest_path.parent),
                    reason="pages_json_not_found",
                )
            )
            continue

        if strict:
            contract_context_raw = out.get("contract_context_json")
            provenance_raw = out.get("provenance_json")
            contract_context_ok = isinstance(contract_context_raw, str) and Path(contract_context_raw).exists()
            provenance_ok = isinstance(provenance_raw, str) and Path(provenance_raw).exists()
            if not contract_context_ok or not provenance_ok:
                results.append(
                    AnalyzerPrepareResult(
                        document_id=document_id,
                        ocid=ocid,
                        status="skipped",
                        bundle_dir=str(manifest_path.parent),
                        reason="missing_bridge_context",
                    )
                )
                continue

        pages = _load_pages_from_bundle(pages_path)
        chunks = chunk_pages(pages, max_chars=max_chars, overlap_chars=overlap_chars)
        flags = detect_flags_in_pages(pages)

        bundle_dir = manifest_path.parent
        chunks_path = bundle_dir / "chunks.json"
        flags_path = bundle_dir / "flags.json"

        chunks_payload = {
            "document_id": document_id,
            "ocid": ocid,
            "chunks": [chunk.model_dump(mode="json") for chunk in chunks],
        }
        chunks_path.write_text(json.dumps(chunks_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        flags_payload = {
            "document_id": document_id,
            "ocid": ocid,
            "flags": [flag.model_dump(mode="json") for flag in flags],
        }
        flags_path.write_text(json.dumps(flags_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        analyzer_entry = {
            "document_id": document_id,
            "ocid": ocid,
            "bundle_dir": str(bundle_dir),
            "inputs": {
                "pages_json": str(pages_path),
                "contract_context_json": str(out.get("contract_context_json") or ""),
                "provenance_json": str(out.get("provenance_json") or ""),
            },
            "outputs": {
                "chunks_json": str(chunks_path),
                "flags_json": str(flags_path),
            },
            "metrics": {
                "pages_count": len(pages),
                "chunks_count": len(chunks),
                "flags_count": len(flags),
            },
        }
        analyzer_index.append(analyzer_entry)

        results.append(
            AnalyzerPrepareResult(
                document_id=document_id,
                ocid=ocid,
                status="ready",
                chunks_count=len(chunks),
                flags_count=len(flags),
                bundle_dir=str(bundle_dir),
            )
        )

    index_path = root / "analyzer_input_manifest.json"
    index_payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "bundles_total": len(results),
        "bundles_ready": sum(1 for result in results if result.status == "ready"),
        "bundles": analyzer_index,
    }
    index_path.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return results


def prepare_loader_inputs(
    bridge_root: Path,
    *,
    limit: int | None = None,
    strict: bool = True,
) -> list[LoaderPrepareResult]:
    root = bridge_root.resolve()
    bundle_manifests = sorted(root.glob("*/bundle_manifest.json"))
    if limit is not None:
        bundle_manifests = bundle_manifests[:limit]

    results: list[LoaderPrepareResult] = []
    loader_index: list[dict[str, Any]] = []

    for manifest_path in bundle_manifests:
        bundle = _read_json(manifest_path)
        document_id = str(bundle.get("document_id") or manifest_path.parent.name)
        ocid = _normalize_ocid(str(bundle.get("ocid") or ""))
        out_raw = bundle.get("outputs")
        out: dict[str, Any] = out_raw if isinstance(out_raw, dict) else {}
        bundle_dir = manifest_path.parent

        chunks_json = bundle_dir / "chunks.json"
        flags_json = bundle_dir / "flags.json"
        if not chunks_json.exists() or not flags_json.exists():
            results.append(
                LoaderPrepareResult(
                    document_id=document_id,
                    ocid=ocid,
                    status="skipped",
                    bundle_dir=str(bundle_dir),
                    reason="missing_analyzer_outputs",
                )
            )
            continue

        contract_context_json = Path(str(out.get("contract_context_json") or ""))
        provenance_json = Path(str(out.get("provenance_json") or ""))
        if strict and (not contract_context_json.exists() or not provenance_json.exists()):
            results.append(
                LoaderPrepareResult(
                    document_id=document_id,
                    ocid=ocid,
                    status="skipped",
                    bundle_dir=str(bundle_dir),
                    reason="missing_bridge_context",
                )
            )
            continue

        contract_payload = _read_json(contract_context_json) if contract_context_json.exists() else {}
        context_raw = contract_payload.get("contract_context")
        context: dict[str, Any] = context_raw if isinstance(context_raw, dict) else {}
        source_url = context.get("source_url") if isinstance(context.get("source_url"), str) else None
        entity_name = context.get("entity_name") if isinstance(context.get("entity_name"), str) else None
        title = f"TDR OCR {ocid or document_id}"

        tdr_manifest_row = {
            "external_id": ocid or document_id,
            "title": title,
            "entity_name": entity_name,
            "procedure_code": ocid,
            "source_url": source_url,
            "file_url": None,
            "sector": None,
            "region": None,
            "district": None,
            "publication_date": None,
            "estimated_value": context.get("monto"),
            "local_path": None,
        }
        manifest_jsonl = bundle_dir / "tdr_manifest.jsonl"
        manifest_jsonl.write_text(json.dumps(tdr_manifest_row, ensure_ascii=False) + "\n", encoding="utf-8")

        loader_entry = {
            "document_id": document_id,
            "ocid": ocid,
            "bundle_dir": str(bundle_dir),
            "manifest_jsonl": str(manifest_jsonl),
            "chunks_json": str(chunks_json),
            "flags_json": str(flags_json),
        }
        loader_index.append(loader_entry)
        results.append(
            LoaderPrepareResult(
                document_id=document_id,
                ocid=ocid,
                status="ready",
                manifest_jsonl=str(manifest_jsonl),
                bundle_dir=str(bundle_dir),
            )
        )

    index_payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "bundles_total": len(results),
        "bundles_ready": sum(1 for result in results if result.status == "ready"),
        "bundles": loader_index,
    }
    (root / "loader_input_manifest.json").write_text(
        json.dumps(index_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return results
