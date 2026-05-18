-- 0002_tdr_core.sql
-- Minimal MVP schema for AgentePerry TDR Scanner.

CREATE TABLE IF NOT EXISTS tdr_documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  external_id text UNIQUE,
  title text NOT NULL,
  entity_name text,
  procedure_code text,
  source_url text,
  file_url text,
  sector text,
  region text,
  district text,
  publication_date date,
  estimated_value numeric,
  storage_path text,
  checksum text,
  raw_text text,
  parse_status text NOT NULL DEFAULT 'pending'
    CHECK (parse_status IN ('pending', 'parsed', 'empty_text', 'failed')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tdr_pages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tdr_id uuid NOT NULL REFERENCES tdr_documents(id) ON DELETE CASCADE,
  page_number int NOT NULL CHECK (page_number > 0),
  text_content text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tdr_id, page_number)
);

CREATE TABLE IF NOT EXISTS tdr_chunks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tdr_id uuid NOT NULL REFERENCES tdr_documents(id) ON DELETE CASCADE,
  chunk_index int NOT NULL CHECK (chunk_index >= 0),
  page_start int NOT NULL CHECK (page_start > 0),
  page_end int NOT NULL CHECK (page_end >= page_start),
  text_content text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tdr_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS tdr_embeddings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chunk_id uuid NOT NULL UNIQUE REFERENCES tdr_chunks(id) ON DELETE CASCADE,
  embedding vector(1536) NOT NULL,
  embedding_model text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tdr_flags (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tdr_id uuid NOT NULL REFERENCES tdr_documents(id) ON DELETE CASCADE,
  chunk_id uuid REFERENCES tdr_chunks(id) ON DELETE SET NULL,
  flag_code text NOT NULL,
  flag_name text NOT NULL,
  severity text NOT NULL CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH')),
  score_contribution int NOT NULL DEFAULT 0 CHECK (score_contribution >= 0 AND score_contribution <= 100),
  evidence_quote text NOT NULL,
  page_number int NOT NULL CHECK (page_number > 0),
  explanation text NOT NULL,
  detection_method text NOT NULL DEFAULT 'rule',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tdr_documents_status ON tdr_documents(parse_status);
CREATE INDEX IF NOT EXISTS idx_tdr_documents_entity ON tdr_documents(entity_name);
CREATE INDEX IF NOT EXISTS idx_tdr_pages_tdr ON tdr_pages(tdr_id, page_number);
CREATE INDEX IF NOT EXISTS idx_tdr_chunks_tdr ON tdr_chunks(tdr_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_tdr_chunks_search ON tdr_chunks
  USING gin (to_tsvector('spanish', coalesce(text_content, '')));
CREATE INDEX IF NOT EXISTS idx_tdr_embeddings_vector ON tdr_embeddings
  USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_tdr_flags_tdr ON tdr_flags(tdr_id);
CREATE INDEX IF NOT EXISTS idx_tdr_flags_code ON tdr_flags(flag_code);

ALTER TABLE tdr_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE tdr_pages ENABLE ROW LEVEL SECURITY;
ALTER TABLE tdr_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE tdr_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE tdr_flags ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tdr_documents_public_read" ON tdr_documents FOR SELECT USING (true);
CREATE POLICY "tdr_pages_public_read" ON tdr_pages FOR SELECT USING (true);
CREATE POLICY "tdr_chunks_public_read" ON tdr_chunks FOR SELECT USING (true);
CREATE POLICY "tdr_embeddings_public_read" ON tdr_embeddings FOR SELECT USING (true);
CREATE POLICY "tdr_flags_public_read" ON tdr_flags FOR SELECT USING (true);
