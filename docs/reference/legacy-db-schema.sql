-- Contralatam Agent — Schema SQL completo
-- PostgreSQL 16 + pgvector
-- Ejecutar: psql -d contralatam < db_schema.sql

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- búsqueda fuzzy de nombres
CREATE EXTENSION IF NOT EXISTS unaccent;  -- búsqueda sin tildes

-- ──────────────────────────────────────────────
-- NÚCLEO DEL GRAFO
-- ──────────────────────────────────────────────

CREATE TABLE entities (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type  VARCHAR(30) NOT NULL CHECK (entity_type IN (
                 'company','public_entity','person','org_politica',
                 'sancion','audit_report','electoral_contribution',
                 'dji','legal_norm')),
  canonical_id VARCHAR(20) UNIQUE,       -- RUC (11d) o DNI (8d)
  display_name TEXT NOT NULL,
  metadata     JSONB NOT NULL DEFAULT '{}',
  risk_score   FLOAT DEFAULT 0 CHECK (risk_score BETWEEN 0 AND 1),
  sources      TEXT[] DEFAULT '{}',
  valid_from   DATE,
  valid_until  DATE,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_entities_type    ON entities(entity_type);
CREATE INDEX idx_entities_cid     ON entities(canonical_id);
CREATE INDEX idx_entities_risk    ON entities(risk_score DESC);
CREATE INDEX idx_entities_meta    ON entities USING GIN(metadata);
CREATE INDEX idx_entities_name    ON entities USING GIN(display_name gin_trgm_ops);

CREATE TABLE relationships (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id   UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  target_id   UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  rel_type    VARCHAR(50) NOT NULL CHECK (rel_type IN (
                'GANO_CONTRATO','COMPRO_A','POSTULO_EN',
                'MIEMBRO_COMITE','FUNCIONARIO_EN','REPRESENTANTE_DE',
                'FAMILIAR_DE','APORTO_A','CANDIDATO_EN','GOVERNS',
                'MISMO_DOMICILIO','MISMO_REPR_LEGAL',
                'TIENE_SANCION','MENCIONADO_EN','VINCULO_DJI',
                'GENERATES_CASE','JUSTIFIES')),
  weight      FLOAT DEFAULT 1.0,
  valid_from  DATE,
  valid_until DATE,
  properties  JSONB NOT NULL DEFAULT '{}',
  data_source VARCHAR(30),
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_rel_source  ON relationships(source_id);
CREATE INDEX idx_rel_target  ON relationships(target_id);
CREATE INDEX idx_rel_type    ON relationships(rel_type);
CREATE INDEX idx_rel_valid   ON relationships(valid_from, valid_until);
CREATE INDEX idx_rel_srctype ON relationships(source_id, rel_type);
CREATE INDEX idx_rel_tgttype ON relationships(target_id, rel_type);

-- ──────────────────────────────────────────────
-- CONTRATOS (detalle OCDS)
-- ──────────────────────────────────────────────

CREATE TABLE contracts (
  ocid            VARCHAR(100) PRIMARY KEY,
  buyer_id        UUID REFERENCES entities(id),
  tender_method   VARCHAR(50),
  tender_method_details VARCHAR(200),
  objeto          TEXT,
  monto_conv      NUMERIC(20,2),
  monto_adj       NUMERIC(20,2),
  monto_contrato  NUMERIC(20,2),
  num_postores    INT,
  fecha_conv      DATE,
  fecha_cierre    DATE,
  fecha_adj       DATE,
  fecha_cont_ini  DATE,
  fecha_cont_fin  DATE,
  dias_plazo_conv INT GENERATED ALWAYS AS (
    CASE WHEN fecha_conv IS NOT NULL AND fecha_cierre IS NOT NULL
         THEN (fecha_cierre - fecha_conv)  -- simplificado; usar función para días hábiles
         ELSE NULL END
  ) STORED,
  delta_monto_pct FLOAT,   -- calculado post-ingesta
  percentil_monto FLOAT,   -- calculado por ventana PERCENT_RANK
  region          VARCHAR(50),
  ubigeo          VARCHAR(6),
  source_year     INT NOT NULL,
  raw_ocds        JSONB
) PARTITION BY LIST (source_year);

-- Crear particiones por año
CREATE TABLE contracts_2022 PARTITION OF contracts FOR VALUES IN (2022);
CREATE TABLE contracts_2023 PARTITION OF contracts FOR VALUES IN (2023);
CREATE TABLE contracts_2024 PARTITION OF contracts FOR VALUES IN (2024);
CREATE TABLE contracts_2025 PARTITION OF contracts FOR VALUES IN (2025);
CREATE TABLE contracts_2026 PARTITION OF contracts FOR VALUES IN (2026);

CREATE INDEX idx_contracts_buyer   ON contracts(buyer_id);
CREATE INDEX idx_contracts_method  ON contracts(tender_method);
CREATE INDEX idx_contracts_region  ON contracts(region);
CREATE INDEX idx_contracts_postores ON contracts(num_postores);
CREATE INDEX idx_contracts_monto   ON contracts(monto_contrato DESC);

-- ──────────────────────────────────────────────
-- RED FLAGS
-- ──────────────────────────────────────────────

CREATE TABLE risk_flags (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  flag_type     VARCHAR(50) NOT NULL,
  pattern_id    VARCHAR(20),            -- pattern_1 ... pattern_8
  score_contrib FLOAT NOT NULL CHECK (score_contrib > 0),
  contract_ocid VARCHAR(100) REFERENCES contracts(ocid),
  entity_a      UUID REFERENCES entities(id),
  entity_b      UUID REFERENCES entities(id),
  evidence      JSONB NOT NULL DEFAULT '{}',
  detected_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_flags_type     ON risk_flags(flag_type);
CREATE INDEX idx_flags_contract ON risk_flags(contract_ocid);
CREATE INDEX idx_flags_entity_a ON risk_flags(entity_a);
CREATE INDEX idx_flags_pattern  ON risk_flags(pattern_id);

-- ──────────────────────────────────────────────
-- CASOS / DOSSIERS PÚBLICOS
-- ──────────────────────────────────────────────

CREATE TABLE risk_cases (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug            VARCHAR(100) UNIQUE NOT NULL,
  score_total     FLOAT NOT NULL CHECK (score_total BETWEEN 0 AND 1),
  nivel_riesgo    VARCHAR(20) NOT NULL CHECK (nivel_riesgo IN ('BAJO','MEDIO','ALTO','CRÍTICO')),
  resumen_llm     TEXT,
  preguntas       TEXT[],
  copy_redes      TEXT,
  disclaimer      TEXT DEFAULT 'Esta información proviene de fuentes públicas oficiales del Estado peruano. No constituye acusación de delito ni determinación de responsabilidad. Las autoridades competentes son las únicas con facultad para determinar responsabilidades.',
  flags           UUID[] DEFAULT '{}',
  entities_involv UUID[] DEFAULT '{}',
  contracts_involv VARCHAR(100)[] DEFAULT '{}',
  ubigeo_caso     VARCHAR(6),
  region          VARCHAR(50),
  zep_session_id  VARCHAR(100),
  publicado       BOOLEAN DEFAULT FALSE,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  CONSTRAINT publish_score CHECK (
    (publicado = FALSE) OR (publicado = TRUE AND score_total >= 0.50)
  )
);

CREATE INDEX idx_cases_score    ON risk_cases(score_total DESC);
CREATE INDEX idx_cases_nivel    ON risk_cases(nivel_riesgo);
CREATE INDEX idx_cases_ubigeo   ON risk_cases(ubigeo_caso);
CREATE INDEX idx_cases_pub      ON risk_cases(publicado);
CREATE INDEX idx_cases_created  ON risk_cases(created_at DESC);

-- ──────────────────────────────────────────────
-- SANCIONES (detalle)
-- ──────────────────────────────────────────────

CREATE TABLE sanciones (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id        UUID REFERENCES entities(id),  -- Person o Company
  numero_resolucion VARCHAR(200) UNIQUE,
  tipo_sancion     VARCHAR(50) CHECK (tipo_sancion IN ('INHABILITACION','SUSPENSION','MULTA','AMONESTACION')),
  fecha_inicio     DATE NOT NULL,
  fecha_fin        DATE,
  vigente          BOOLEAN GENERATED ALWAYS AS (
    fecha_fin IS NULL OR fecha_fin >= CURRENT_DATE
  ) STORED,
  entidad_nombre   TEXT,
  causal           TEXT,
  fuente_fecha     DATE  -- fecha del XLSX descargado de Contraloría
);

CREATE INDEX idx_sanciones_entity  ON sanciones(entity_id);
CREATE INDEX idx_sanciones_vigente ON sanciones(vigente) WHERE vigente = TRUE;
CREATE INDEX idx_sanciones_tipo    ON sanciones(tipo_sancion);

-- ──────────────────────────────────────────────
-- DJI — DECLARACIONES DE INTERESES
-- ──────────────────────────────────────────────

CREATE TABLE interest_declarations (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_id         UUID REFERENCES entities(id),  -- Person
  funcionario_dni   VARCHAR(8),
  cargo             TEXT,
  entidad_nombre    TEXT,
  periodo           VARCHAR(20),
  vinculos_empresariales JSONB DEFAULT '[]',  -- [{ruc, empresa, tipo, participacion}]
  familiares        JSONB DEFAULT '[]',        -- [{nombre, parentesco, actividad}]
  actividades_priv  JSONB DEFAULT '[]',
  fecha_presentacion DATE,
  fuente_scrape_date DATE
);

CREATE INDEX idx_dji_dni     ON interest_declarations(funcionario_dni);
CREATE INDEX idx_dji_vinculos ON interest_declarations USING GIN(vinculos_empresariales);
CREATE INDEX idx_dji_familiares ON interest_declarations USING GIN(familiares);

-- ──────────────────────────────────────────────
-- APORTES ELECTORALES
-- ──────────────────────────────────────────────

CREATE TABLE electoral_contributions (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  aportante_ruc    VARCHAR(11),   -- FK lógica a entities(canonical_id)
  aportante_dni    VARCHAR(8),
  aportante_nombre TEXT,
  org_politica_id  UUID REFERENCES entities(id),
  monto            NUMERIC(15,2),
  tipo_aporte      VARCHAR(20) CHECK (tipo_aporte IN ('DINERO','ESPECIE')),
  campana          VARCHAR(100),
  proceso_electoral VARCHAR(50),
  fecha_aporte     DATE,
  fuente_scrape_date DATE
);

CREATE INDEX idx_aportes_ruc  ON electoral_contributions(aportante_ruc);
CREATE INDEX idx_aportes_fecha ON electoral_contributions(fecha_aporte);
CREATE INDEX idx_aportes_org  ON electoral_contributions(org_politica_id);

-- ──────────────────────────────────────────────
-- RAG LEGAL
-- ──────────────────────────────────────────────

CREATE TABLE legal_chunks (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  norma_num VARCHAR(20),
  tipo_norma VARCHAR(20),
  articulo  VARCHAR(20),
  texto     TEXT NOT NULL,
  embedding VECTOR(1536),
  tags      TEXT[] DEFAULT '{}'
);

CREATE INDEX idx_legal_vec ON legal_chunks
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_legal_tags ON legal_chunks USING GIN(tags);

-- ──────────────────────────────────────────────
-- ALERTAS SMS
-- ──────────────────────────────────────────────

CREATE TABLE alert_subscriptions (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  phone     VARCHAR(15) NOT NULL,
  ubigeo    VARCHAR(6)  NOT NULL,
  opt_in_at TIMESTAMPTZ DEFAULT NOW(),
  active    BOOLEAN DEFAULT TRUE,
  UNIQUE(phone, ubigeo)
);

CREATE TABLE alert_messages (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id     UUID REFERENCES risk_cases(id),
  phone       VARCHAR(15),
  mensaje     TEXT,
  sent_at     TIMESTAMPTZ,
  status      VARCHAR(20),  -- sent|failed|pending
  provider_id VARCHAR(100)  -- ID de Zavu
);

-- ──────────────────────────────────────────────
-- FUNCIONES ÚTILES
-- ──────────────────────────────────────────────

-- Subgrafo recursivo desde un canonical_id (RUC o DNI)
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
    FROM entities WHERE canonical_id = p_canonical_id

    UNION ALL

    SELECT e.id, e.display_name, e.entity_type, sg.depth + 1, sg.path || e.id
    FROM entities e
    JOIN relationships r ON (r.source_id = sg.node_id OR r.target_id = sg.node_id)
      AND (e.id = r.target_id OR e.id = r.source_id)
      AND e.id != sg.node_id
    JOIN subgraph sg ON TRUE
    WHERE sg.depth < p_max_depth
      AND NOT e.id = ANY(sg.path)
      AND (r.valid_until IS NULL OR r.valid_until >= p_check_date)
  )
  SELECT DISTINCT id AS node_id, display_name, entity_type, depth, path
  FROM subgraph
  ORDER BY depth;
$$ LANGUAGE sql STABLE;

-- Nivel de riesgo desde score numérico
CREATE OR REPLACE FUNCTION score_to_nivel(p_score FLOAT)
RETURNS VARCHAR AS $$
  SELECT CASE
    WHEN p_score >= 0.75 THEN 'CRÍTICO'
    WHEN p_score >= 0.50 THEN 'ALTO'
    WHEN p_score >= 0.30 THEN 'MEDIO'
    ELSE 'BAJO'
  END;
$$ LANGUAGE sql IMMUTABLE;

-- Trigger: actualizar updated_at
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_entities_updated
  BEFORE UPDATE ON entities
  FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trg_cases_updated
  BEFORE UPDATE ON risk_cases
  FOR EACH ROW EXECUTE FUNCTION update_timestamp();
