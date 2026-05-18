-- Migration 0004: Add graph_findings and related fields to tdr_documents
-- Required by: SPEC-0005 (dossier API with graph enrichment), SPEC-0012 (Neo4j integration).
-- Requires: 0002_tdr_core.sql (tdr_documents base table).

ALTER TABLE tdr_documents
  ADD COLUMN IF NOT EXISTS dossier_path TEXT,
  ADD COLUMN IF NOT EXISTS graph_enrichment_status TEXT
    NOT NULL DEFAULT 'pending'
    CHECK (graph_enrichment_status IN ('pending', 'enriched', 'error', 'skipped')),
  ADD COLUMN IF NOT EXISTS graph_findings JSONB
    NOT NULL DEFAULT '{"signals": [], "risk_delta": 0, "error": null}'::jsonb;

COMMENT ON COLUMN tdr_documents.dossier_path IS
  'Absolute path to the generated dossier.md file for this TDR.';
COMMENT ON COLUMN tdr_documents.graph_enrichment_status IS
  'Whether graph enrichment via Neo4j has been applied: pending|enriched|error|skipped.';
COMMENT ON COLUMN tdr_documents.graph_findings IS
  'JSON object with graph enrichment results: signals[], risk_delta, community_size, etc.';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_tdr_documents_graph_status
  ON tdr_documents(graph_enrichment_status);
CREATE INDEX IF NOT EXISTS idx_tdr_documents_dossier_path
  ON tdr_documents(dossier_path)
  WHERE dossier_path IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tdr_documents_graph_findings
  ON tdr_documents USING gin(graph_findings);
