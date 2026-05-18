-- Migration: Add pgvector similarity search function for TDR chunks
-- Requires: 0002_tdr_core.sql (embedding table with vector column)

CREATE OR REPLACE FUNCTION match_tdr_chunks(
  query_embedding vector(1536),
  match_threshold float DEFAULT 0.3,
  match_count int DEFAULT 10
)
RETURNS TABLE (
  tdr_id uuid,
  chunk_text text,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    tc.tdr_id,
    tc.text_content AS chunk_text,
    1 - (te.embedding <=> query_embedding) AS similarity
  FROM tdr_embeddings te
  JOIN tdr_chunks tc ON tc.id = te.chunk_id
  WHERE 1 - (te.embedding <=> query_embedding) >= match_threshold
  ORDER BY te.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;