"""Sync parsed TDR pipeline output (pages, chunks, embeddings, flags) to Supabase."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agenteperry.db.client import DbClient
from agenteperry.tdr.models import TdrChunk, TdrDocumentMetadata, TdrFlag, TdrPage

db = DbClient()


def upsert_tdr_document(meta: TdrDocumentMetadata) -> str:
    """Upsert a TDR document record. Returns the document UUID."""
    query = """
        INSERT INTO tdr_documents (
            external_id, title, entity_name, source_url, file_url,
            procedure_code, sector, region, district,
            publication_date, estimated_value, parse_status
        ) VALUES (
            %(external_id)s, %(title)s, %(entity_name)s, %(source_url)s, %(file_url)s,
            %(procedure_code)s, %(sector)s, %(region)s, %(district)s,
            %(publication_date)s, %(estimated_value)s, 'parsed'
        )
        ON CONFLICT (external_id) DO UPDATE SET
            title = EXCLUDED.title,
            entity_name = EXCLUDED.entity_name,
            source_url = EXCLUDED.source_url,
            file_url = EXCLUDED.file_url,
            procedure_code = EXCLUDED.procedure_code,
            sector = EXCLUDED.sector,
            region = EXCLUDED.region,
            district = EXCLUDED.district,
            publication_date = EXCLUDED.publication_date,
            estimated_value = EXCLUDED.estimated_value,
            parse_status = 'parsed',
            updated_at = now()
        RETURNING id
    """
    params = meta.model_dump()
    params.pop("local_path", None)
    result = db.execute(query, params)
    return str(result[0]["id"]) if result else ""


def upsert_tdr_document_v2(
    meta: TdrDocumentMetadata,
    dossier_path: str | None = None,
    graph_enrichment_status: str | None = None,
    graph_findings: dict[str, Any] | None = None,
) -> str:
    """Upsert a TDR document record with graph enrichment fields.

    ``graph_enrichment_status`` must be one of: pending, enriched, error, skipped.
    ``graph_findings`` is the JSON object returned by ``enrich_dossier_with_graph``.
    """
    status_map = {"pending", "enriched", "error", "skipped"}
    effective_status = (
        graph_enrichment_status
        if graph_enrichment_status in status_map
        else "pending"
    )
    query = """
        INSERT INTO tdr_documents (
            external_id, title, entity_name, source_url, file_url,
            procedure_code, sector, region, district,
            publication_date, estimated_value, parse_status,
            dossier_path, graph_enrichment_status, graph_findings
        ) VALUES (
            %(external_id)s, %(title)s, %(entity_name)s, %(source_url)s, %(file_url)s,
            %(procedure_code)s, %(sector)s, %(region)s, %(district)s,
            %(publication_date)s, %(estimated_value)s, 'parsed',
            %(dossier_path)s, %(graph_enrichment_status)s, %(graph_findings)s::jsonb
        )
        ON CONFLICT (external_id) DO UPDATE SET
            title = EXCLUDED.title,
            entity_name = EXCLUDED.entity_name,
            source_url = EXCLUDED.source_url,
            file_url = EXCLUDED.file_url,
            procedure_code = EXCLUDED.procedure_code,
            sector = EXCLUDED.sector,
            region = EXCLUDED.region,
            district = EXCLUDED.district,
            publication_date = EXCLUDED.publication_date,
            estimated_value = EXCLUDED.estimated_value,
            parse_status = 'parsed',
            dossier_path = COALESCE(EXCLUDED.dossier_path, tdr_documents.dossier_path),
            graph_enrichment_status = EXCLUDED.graph_enrichment_status,
            graph_findings = COALESCE(EXCLUDED.graph_findings, tdr_documents.graph_findings),
            updated_at = now()
        RETURNING id
    """
    params = meta.model_dump()
    params.pop("local_path", None)
    params["dossier_path"] = dossier_path
    params["graph_enrichment_status"] = effective_status
    params["graph_findings"] = (
        json.dumps(graph_findings) if graph_findings else None
    )
    result = db.execute(query, params)
    return str(result[0]["id"]) if result else ""


def update_tdr_graph_fields(
    external_id: str,
    dossier_path: str | None = None,
    graph_enrichment_status: str | None = None,
    graph_findings: dict[str, Any] | None = None,
) -> None:
    """Update graph enrichment fields on an existing tdr_documents record.

    Use after ``upsert_tdr_document`` when graph enrichment completes
    in a separate step (CDC pipeline, auditor, etc.).
    """
    status_map = {"pending", "enriched", "error", "skipped"}
    effective_status = (
        graph_enrichment_status
        if graph_enrichment_status in status_map
        else "pending"
    )
    query = """
        UPDATE tdr_documents SET
            dossier_path = COALESCE(%(dossier_path)s, dossier_path),
            graph_enrichment_status = COALESCE(%(graph_enrichment_status)s, graph_enrichment_status),
            graph_findings = COALESCE(%(graph_findings)s::jsonb, graph_findings),
            updated_at = now()
        WHERE external_id = %(external_id)s
    """
    db.execute(
        query,
        {
            "external_id": external_id,
            "dossier_path": dossier_path,
            "graph_enrichment_status": effective_status,
            "graph_findings": json.dumps(graph_findings) if graph_findings else None,
        },
    )


def upsert_tdr_pages(tdr_uuid: str, pages: list[TdrPage]) -> int:
    """Upsert pages for a TDR document."""
    if not pages:
        return 0
    query = """
        INSERT INTO tdr_pages (tdr_id, page_number, text_content)
        VALUES (%(tdr_id)s, %(page_number)s, %(text_content)s)
        ON CONFLICT (tdr_id, page_number) DO UPDATE SET
            text_content = EXCLUDED.text_content
    """
    params_list = [{"tdr_id": tdr_uuid, "page_number": p.page_number, "text_content": p.text_content} for p in pages]
    db.execute_batch(query, params_list)
    return len(pages)


def upsert_tdr_chunks(tdr_uuid: str, chunks: list[TdrChunk]) -> int:
    """Upsert chunks for a TDR document."""
    if not chunks:
        return 0
    query = """
        INSERT INTO tdr_chunks (tdr_id, chunk_index, page_start, page_end, text_content, metadata)
        VALUES (%(tdr_id)s, %(chunk_index)s, %(page_start)s, %(page_end)s, %(text_content)s, %(metadata)s::jsonb)
        ON CONFLICT (tdr_id, chunk_index) DO UPDATE SET
            page_start = EXCLUDED.page_start,
            page_end = EXCLUDED.page_end,
            text_content = EXCLUDED.text_content,
            metadata = EXCLUDED.metadata
    """
    params_list = [
        {
            "tdr_id": tdr_uuid,
            "chunk_index": c.chunk_index,
            "page_start": c.page_start,
            "page_end": c.page_end,
            "text_content": c.text,
            "metadata": json.dumps(c.metadata),
        }
        for c in chunks
    ]
    db.execute_batch(query, params_list)
    return len(chunks)


def upsert_tdr_flags(tdr_uuid: str, flags: list[TdrFlag]) -> int:
    """Upsert flags for a TDR document."""
    if not flags:
        return 0
    query = """
        INSERT INTO tdr_flags (
            tdr_id, flag_code, flag_name, severity,
            score_contribution, evidence_quote, page_number,
            explanation, detection_method, rule_id
        ) VALUES (
            %(tdr_id)s, %(flag_code)s, %(flag_name)s, %(severity)s,
            %(score_contribution)s, %(evidence_quote)s, %(page_number)s,
            %(explanation)s, %(detection_method)s, %(rule_id)s
        )
        ON CONFLICT DO NOTHING
    """
    params_list = [
        {
            "tdr_id": tdr_uuid,
            "flag_code": f.flag_code,
            "flag_name": f.flag_name,
            "severity": f.severity,
            "score_contribution": f.score_contribution,
            "evidence_quote": f.evidence_quote,
            "page_number": f.page_number,
            "explanation": f.explanation,
            "detection_method": f.detection_method,
            "rule_id": f.rule_id,
        }
        for f in flags
    ]
    db.execute_batch(query, params_list)
    return len(flags)


def upsert_tdr_embeddings(chunks_with_embeddings: list[dict[str, Any]], embedding_model: str = "text-embedding-3-small") -> int:
    """Upsert embeddings given a list of {chunk_id, embedding} dicts."""
    if not chunks_with_embeddings:
        return 0
    query = """
        INSERT INTO tdr_embeddings (chunk_id, embedding, embedding_model)
        VALUES (%(chunk_id)s, %(embedding)s::vector, %(embedding_model)s)
        ON CONFLICT (chunk_id) DO UPDATE SET
            embedding = EXCLUDED.embedding,
            embedding_model = EXCLUDED.embedding_model
    """
    params_list = [
        {
            "chunk_id": r["chunk_id"],
            "embedding": "[" + ",".join(str(x) for x in r["embedding"]) + "]",
            "embedding_model": embedding_model,
        }
        for r in chunks_with_embeddings
    ]
    db.execute_batch(query, params_list)
    return len(chunks_with_embeddings)


def load_pipeline_json(
    manifest_json: Path,
    pages_json: Path | None = None,
    chunks_json: Path | None = None,
    flags_json: Path | None = None,
    embeddings_json: Path | None = None,
) -> dict[str, int]:
    """Load a complete TDR pipeline result from JSON files into the database.

    Expected structure of manifest_json (one TDR per line JSONL):
        {"external_id": "...", "title": "...", "entity_name": "...",
         "procedure_code": "...", "publication_date": "...", ...}

    All other paths are JSON files produced by the TDR CLI pipeline.
    """
    counts: dict[str, int] = {}

    meta_records = _load_jsonl(manifest_json)
    for meta_dict in meta_records:
        meta = TdrDocumentMetadata.model_validate(meta_dict)
        tdr_uuid = upsert_tdr_document(meta)
        counts["tdr_documents"] = counts.get("tdr_documents", 0) + 1

    if pages_json and pages_json.exists():
        payload = json.loads(pages_json.read_text(encoding="utf-8"))
        pages = [TdrPage.model_validate(p) for p in payload.get("pages", [])]
        if pages:
            first_meta = TdrDocumentMetadata.model_validate(meta_records[0])
            tdr_uuid = upsert_tdr_document(first_meta)
            counts["tdr_pages"] = upsert_tdr_pages(tdr_uuid, pages)

    if chunks_json and chunks_json.exists():
        payload = json.loads(chunks_json.read_text(encoding="utf-8"))
        chunks = [TdrChunk.model_validate(c) for c in payload.get("chunks", [])]
        if chunks:
            first_meta = TdrDocumentMetadata.model_validate(meta_records[0])
            tdr_uuid = upsert_tdr_document(first_meta)
            counts["tdr_chunks"] = upsert_tdr_chunks(tdr_uuid, chunks)

    if flags_json and flags_json.exists():
        payload = json.loads(flags_json.read_text(encoding="utf-8"))
        flags = [TdrFlag.model_validate(f) for f in payload.get("flags", [])]
        if flags:
            first_meta = TdrDocumentMetadata.model_validate(meta_records[0])
            tdr_uuid = upsert_tdr_document(first_meta)
            counts["tdr_flags"] = upsert_tdr_flags(tdr_uuid, flags)

    if embeddings_json and embeddings_json.exists():
        embeds = _load_jsonl(embeddings_json)
        if embeds:
            first_meta = TdrDocumentMetadata.model_validate(meta_records[0])
            tdr_uuid = upsert_tdr_document(first_meta)
            counts["tdr_embeddings"] = upsert_tdr_embeddings(embeds)

    return counts


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            records.append(json.loads(stripped))
    return records