-- 0001_extensions.sql
-- Postgres extensions for AgentePerry TDR Scanner.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";       -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "vector";          -- pgvector for embeddings
CREATE EXTENSION IF NOT EXISTS "pg_trgm";         -- fuzzy text search
CREATE EXTENSION IF NOT EXISTS "unaccent";        -- accent-insensitive search
CREATE EXTENSION IF NOT EXISTS "btree_gin";       -- composite indexes
