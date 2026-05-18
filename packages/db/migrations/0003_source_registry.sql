-- 0003_source_registry.sql
-- Source registry, graph foundation and RAG tables.
-- Adds generic multi-source support on top of TDR core (0002).

-- ============================================================
-- SOURCE CATALOG — registry of all data sources
-- ============================================================

CREATE TABLE IF NOT EXISTS source_catalog (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_code   VARCHAR(30) UNIQUE NOT NULL,
  source_name   TEXT NOT NULL,
  source_url    TEXT,
  source_type   VARCHAR(20) NOT NULL CHECK (source_type IN (
                'api','bulk_download','playwright','form_scraping',
                'ckan','manual','reference')),
  priority      VARCHAR(5) NOT NULL CHECK (priority IN ('P0','P1','P2','P3')),
  status        VARCHAR(20) NOT NULL DEFAULT 'planned'
                CHECK (status IN ('planned','active','paused','deprecated')),
  license_note  TEXT,
  update_freq   VARCHAR(20),
  owner         VARCHAR(50),
  method_notes  TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_source_catalog_priority ON source_catalog(priority);
CREATE INDEX IF NOT EXISTS idx_source_catalog_status ON source_catalog(status);

-- Seed with legacy sources
INSERT INTO source_catalog (source_code, source_name, source_url, source_type, priority, status, owner, method_notes)
VALUES
  ('ocds_peru', 'OCDS Peru — Open Contracting Data Registry', 'https://data.open-contracting.org/es/publication/135', 'bulk_download', 'P0', 'planned', 'core', 'Direct download JSONL.gz/CSV by year'),
  ('sunat_padron', 'SUNAT — Padron Reducido del RUC', 'https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html', 'bulk_download', 'P0', 'planned', 'core', 'ZIP download, parse TXT pipe-delimited ISO-8859-1'),
  ('sunat_multi_ruc', 'SUNAT — Consulta multiple de RUC', 'https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsmulruc/jrmS00Alias', 'form_scraping', 'P1', 'planned', 'core', 'Form POST with ZIP file, CAPTCHA, max 100 RUC'),
  ('contraloria_sanciones', 'Contraloria — Registro de sanciones', 'https://www.gob.pe/institucion/contraloria/informes-publicaciones/2706979-registro-de-sanciones-inscritas-y-vigentes', 'playwright', 'P0', 'planned', 'core', 'Playwright download intercept XLSX'),
  ('cgr_informes', 'CGR — Buscador de informes de control', 'https://appbp.contraloria.gob.pe/BuscadorCGR/informes/Avanzado.html', 'playwright', 'P1', 'planned', 'core', 'Playwright XHR intercept + PDF'),
  ('seace_oece', 'SEACE/OECE — Portal datos abiertos', 'https://bi.seace.gob.pe/pentaho/api/repos/:public:portal:datosabiertos.html/content?userid=public&password=key', 'bulk_download', 'P0', 'planned', 'core', 'Pentaho direct download CSV/XLSX by category/year'),
  ('ley_32069', 'Ley 32069 — Ley General de Contrataciones Publicas', 'https://www.gob.pe/institucion/oece/colecciones/45029-ley-n-32069-ley-general-de-contrataciones-publicas-y-su-reglamento', 'reference', 'P0', 'active', 'core', 'PDF legal reference, index for RAG'),
  ('sidji_dji', 'SIDJI — Declaraciones Juradas de Intereses', 'https://appdji.contraloria.gob.pe/djic/', 'playwright', 'P1', 'planned', 'core', 'On-demand only, CAPTCHA, no mass scraping'),
  ('mef_transparencia', 'MEF — Transparencia Economica', 'https://www.mef.gob.pe/es/portal-de-transparencia-economica', 'api', 'P1', 'planned', 'core', 'CKAN API or controlled scraping'),
  ('mef_datos_abiertos', 'MEF — Datos Abiertos', 'https://datosabiertos.mef.gob.pe/dataset', 'ckan', 'P1', 'planned', 'core', 'CKAN API package_list / package_search'),
  ('onpe_claridad', 'ONPE — Claridad', 'https://claridadportal.onpe.gob.pe/', 'playwright', 'P1', 'planned', 'core', 'XHR intercept, search by RUC/DNI/org'),
  ('jne_voto_informado', 'JNE — Voto Informado', 'https://votoinformado.jne.gob.pe/', 'playwright', 'P1', 'planned', 'core', 'XHR intercept Angular SPA'),
  ('jne_plataforma', 'JNE — Plataforma Electoral', 'https://plataformaelectoral.jne.gob.pe/', 'playwright', 'P1', 'planned', 'core', 'XHR intercept'),
  ('congreso_leyes', 'Congreso — Archivo Digital de Legislacion', 'https://www.leyes.congreso.gob.pe/', 'form_scraping', 'P1', 'planned', 'core', 'ASP.NET WebForms, HTML table + PDF'),
  ('congreso_proyectos', 'Congreso — Proyectos de Ley', 'https://www.congreso.gob.pe/', 'form_scraping', 'P2', 'planned', 'core', 'Controlled scraping + PDFs'),
  ('sunarp_conoce', 'SUNARP — Conoce Aqui', 'https://conoce-aqui.sunarp.gob.pe/', 'manual', 'P2', 'planned', 'core', 'Requires DNI/date/partida, no mass scraping'),
  ('sunarp_sprl', 'SUNARP — SPRL', 'https://sprl.sunarp.gob.pe/', 'manual', 'P3', 'planned', 'core', 'Paid access, review TOS first'),
  ('sunarp_pj', 'SUNARP — Directorio Personas Juridicas', 'https://www.sunarp.gob.pe/dn-personas-juridicas.asp', 'form_scraping', 'P2', 'planned', 'core', 'Controlled search by denomination'),
  ('poder_judicial', 'Poder Judicial', 'https://www.pj.gob.pe/', 'manual', 'P3', 'planned', 'core', 'Only firm public sentences, human review'),
  ('ministerio_publico', 'Ministerio Publico', 'https://www.gob.pe/mpfn', 'manual', 'P3', 'planned', 'core', 'Official notes only, no automation'),
  ('ojo_publico_funes', 'Ojo Publico — FUNES', 'https://ojo-publico.com/especiales/funes/metodologia.html', 'reference', 'P1', 'active', 'core', 'Methodology reference, do not copy data'),
  ('open_contracting_memoria', 'Open Contracting — Memoria', 'https://www.open-contracting.org/es/2020/09/10/memoria-contra-la-corrupcion-datos-y-algoritmos-para-investigar-compras-publicas/', 'reference', 'P1', 'active', 'core', 'Methodology reference'),
  ('convoca_contrataciones', 'Convoca — Contrataciones', 'https://convoca.pe/tags/contrataciones-publicas', 'form_scraping', 'P1', 'planned', 'core', 'Drupal 9, save only URL/title/snippet'),
  ('convoca_pandemia', 'Convoca — Expedientes Pandemia', 'https://convoca.pe/especiales/expedientes-de-la-pandemia', 'form_scraping', 'P2', 'planned', 'core', 'Manual/semiautomated enrichment')
ON CONFLICT (source_code) DO NOTHING;

-- ============================================================
-- SOURCE RECORDS — generic raw records from any source
-- ============================================================

CREATE TABLE IF NOT EXISTS source_records (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id       UUID NOT NULL REFERENCES source_catalog(id),
  external_id     TEXT,
  record_type     VARCHAR(50) NOT NULL DEFAULT 'unknown',
  raw_data        JSONB NOT NULL DEFAULT '{}',
  parsed_data     JSONB NOT NULL DEFAULT '{}',
  checksum        TEXT,
  fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  retrieved_by    TEXT NOT NULL DEFAULT 'unknown',
  raw_path        TEXT,
  content_type    VARCHAR(50),
  period_year     INT,
  region          VARCHAR(50),
  entity_name     TEXT,
  entity_ruc      VARCHAR(11),
  supplier_name   TEXT,
  supplier_ruc    VARCHAR(11),
  monto           NUMERIC(20,2),
  fecha           DATE,
  source_url      TEXT,
  page_number     INT,
  evidence_quote  TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_source_records_source ON source_records(source_id);
CREATE INDEX IF NOT EXISTS idx_source_records_external ON source_records(external_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_source_records_external_id ON source_records(external_id);
CREATE INDEX IF NOT EXISTS idx_source_records_entity_ruc ON source_records(entity_ruc);
CREATE INDEX IF NOT EXISTS idx_source_records_supplier_ruc ON source_records(supplier_ruc);
CREATE INDEX IF NOT EXISTS idx_source_records_period ON source_records(period_year);
CREATE INDEX IF NOT EXISTS idx_source_records_fecha ON source_records(fecha);
CREATE INDEX IF NOT EXISTS idx_source_records_type ON source_records(record_type);

-- ============================================================
-- SOURCE ENTITIES — normalized entities (graph nodes)
-- ============================================================

CREATE TABLE IF NOT EXISTS source_entities (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type   VARCHAR(30) NOT NULL CHECK (entity_type IN (
                'company','public_entity','person','political_org',
                'sancion','audit_report','electoral_contribution',
                'interest_declaration','legal_norm')),
  canonical_id  VARCHAR(20) UNIQUE,
  display_name  TEXT NOT NULL,
  metadata      JSONB NOT NULL DEFAULT '{}',
  risk_score    FLOAT DEFAULT 0 CHECK (risk_score BETWEEN 0 AND 1),
  sources       TEXT[] DEFAULT '{}',
  valid_from    DATE,
  valid_until   DATE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON source_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_cid ON source_entities(canonical_id);
CREATE INDEX IF NOT EXISTS idx_entities_risk ON source_entities(risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_entities_meta ON source_entities USING GIN(metadata);
CREATE INDEX IF NOT EXISTS idx_entities_name ON source_entities USING GIN(display_name gin_trgm_ops);

-- ============================================================
-- SOURCE RELATIONSHIPS — graph edges in Postgres
-- ============================================================

CREATE TABLE IF NOT EXISTS source_relationships (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id   UUID NOT NULL REFERENCES source_entities(id) ON DELETE CASCADE,
  target_id   UUID NOT NULL REFERENCES source_entities(id) ON DELETE CASCADE,
  rel_type    VARCHAR(50) NOT NULL CHECK (rel_type IN (
                'GANO_CONTRATO','COMPRO_A','POSTULO_EN',
                'MIEMBRO_COMITE','FUNCIONARIO_EN','REPRESENTANTE_DE',
                'FAMILIAR_DE','APORTO_A','CANDIDATO_EN','GOVERNS',
                'MISMO_DOMICILIO','MISMO_REPR_LEGAL',
                'TIENE_SANCION','MENCIONADO_EN','VINCULO_DJI',
                'GENERA_CASO','JUSTIFICA')),
  weight      FLOAT DEFAULT 1.0,
  valid_from  DATE,
  valid_until DATE,
  properties  JSONB NOT NULL DEFAULT '{}',
  data_source VARCHAR(30),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rel_source ON source_relationships(source_id);
CREATE INDEX IF NOT EXISTS idx_rel_target ON source_relationships(target_id);
CREATE INDEX IF NOT EXISTS idx_rel_type ON source_relationships(rel_type);
CREATE INDEX IF NOT EXISTS idx_rel_valid ON source_relationships(valid_from, valid_until);
CREATE INDEX IF NOT EXISTS idx_rel_srctype ON source_relationships(source_id, rel_type);
CREATE INDEX IF NOT EXISTS idx_rel_tgttype ON source_relationships(target_id, rel_type);
CREATE UNIQUE INDEX IF NOT EXISTS uq_source_relationships_src_tgt_type
  ON source_relationships(source_id, target_id, rel_type);

-- ============================================================
-- DOCUMENT CHUNKS — generic text chunks for RAG
-- ============================================================

CREATE TABLE IF NOT EXISTS document_chunks (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_type VARCHAR(30) NOT NULL CHECK (source_type IN (
                'tdr','ley','informe','contrato','norma','articulo')),
  source_id   UUID,
  external_ref TEXT,
  chunk_index INT NOT NULL CHECK (chunk_index >= 0),
  page_start  INT,
  page_end    INT,
  text_content TEXT NOT NULL,
  metadata    JSONB NOT NULL DEFAULT '{}',
  tags        TEXT[] DEFAULT '{}',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_doc_chunks_source ON document_chunks(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_doc_chunks_search ON document_chunks
  USING gin (to_tsvector('spanish', coalesce(text_content, '')));
CREATE INDEX IF NOT EXISTS idx_doc_chunks_tags ON document_chunks USING GIN(tags);
CREATE UNIQUE INDEX IF NOT EXISTS uq_document_chunks_source_ref_idx
  ON document_chunks(source_type, external_ref, chunk_index);

-- ============================================================
-- DOCUMENT EMBEDDINGS — pgvector for semantic search
-- ============================================================

CREATE TABLE IF NOT EXISTS document_embeddings (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chunk_id        UUID NOT NULL UNIQUE REFERENCES document_chunks(id) ON DELETE CASCADE,
  embedding       vector(1536) NOT NULL,
  embedding_model TEXT NOT NULL DEFAULT 'text-embedding-3-small',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_doc_embeddings_vector ON document_embeddings
  USING hnsw (embedding vector_cosine_ops);

-- ============================================================
-- EVIDENCE FLAGS — cross-source flags with traceability
-- ============================================================

CREATE TABLE IF NOT EXISTS evidence_flags (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  flag_code       TEXT NOT NULL,
  flag_name       TEXT NOT NULL,
  severity        TEXT NOT NULL CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
  score_contribution INT NOT NULL DEFAULT 0 CHECK (score_contribution >= 0 AND score_contribution <= 100),
  entity_a_id     UUID REFERENCES source_entities(id),
  entity_b_id     UUID REFERENCES source_entities(id),
  record_id       UUID REFERENCES source_records(id),
  evidence_quote  TEXT NOT NULL,
  page_number     INT,
  explanation     TEXT NOT NULL,
  detection_method TEXT NOT NULL DEFAULT 'rule',
  pattern_id      VARCHAR(20),
  source_url      TEXT,
  data_sources    TEXT[] DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_evidence_flags_code ON evidence_flags(flag_code);
CREATE INDEX IF NOT EXISTS idx_evidence_flags_entity_a ON evidence_flags(entity_a_id);
CREATE INDEX IF NOT EXISTS idx_evidence_flags_entity_b ON evidence_flags(entity_b_id);
CREATE INDEX IF NOT EXISTS idx_evidence_flags_pattern ON evidence_flags(pattern_id);
CREATE INDEX IF NOT EXISTS idx_evidence_flags_severity ON evidence_flags(severity);

-- ============================================================
-- RLS POLICIES
-- ============================================================

ALTER TABLE source_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence_flags ENABLE ROW LEVEL SECURITY;

CREATE POLICY "source_catalog_public_read" ON source_catalog FOR SELECT USING (true);
CREATE POLICY "source_records_public_read" ON source_records FOR SELECT USING (true);
CREATE POLICY "source_entities_public_read" ON source_entities FOR SELECT USING (true);
CREATE POLICY "source_relationships_public_read" ON source_relationships FOR SELECT USING (true);
CREATE POLICY "document_chunks_public_read" ON document_chunks FOR SELECT USING (true);
CREATE POLICY "document_embeddings_public_read" ON document_embeddings FOR SELECT USING (true);
CREATE POLICY "evidence_flags_public_read" ON evidence_flags FOR SELECT USING (true);

-- ============================================================
-- UTILITY FUNCTION: subgraph traversal
-- ============================================================

CREATE OR REPLACE FUNCTION get_subgraph(
  p_canonical_id VARCHAR,
  p_max_depth INT DEFAULT 3,
  p_check_date DATE DEFAULT CURRENT_DATE
)
RETURNS TABLE(
  node_id UUID,
  display_name TEXT,
  entity_type VARCHAR,
  depth INT,
  path UUID[]
) AS $$
  WITH RECURSIVE subgraph AS (
    SELECT id, display_name, entity_type, 0 AS depth, ARRAY[id] AS path
    FROM source_entities WHERE canonical_id = p_canonical_id

    UNION ALL

    SELECT e.id, e.display_name, e.entity_type, prev.depth + 1, prev.path || e.id
    FROM (
      SELECT id, depth, path FROM subgraph
    ) prev
    JOIN source_relationships r ON r.source_id = prev.id OR r.target_id = prev.id
    JOIN source_entities e ON e.id = CASE WHEN r.source_id = prev.id THEN r.target_id ELSE r.source_id END
    WHERE e.id != prev.id
      AND prev.depth < p_max_depth
      AND NOT e.id = ANY(prev.path)
      AND (r.valid_until IS NULL OR r.valid_until >= p_check_date)
  )
  SELECT DISTINCT id AS node_id, display_name, entity_type, depth, path
  FROM subgraph
  ORDER BY depth;
$$ LANGUAGE sql STABLE;
