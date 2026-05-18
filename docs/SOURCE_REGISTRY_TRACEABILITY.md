# Source Registry Traceability

Esta guia explica como ver, auditar, subir y chunkear data OCDS sin perder metadata.

## 1. Flujo completo

```text
OCDS .jsonl.gz oficial
  -> sources collect
  -> source_records JSONL
  -> graph map-records
  -> source_entities + source_relationships JSON
  -> db sync
  -> Postgres/Supabase
  -> db chunk-contracts
  -> document_chunks
  -> web /contracts
```

## 2. Archivo fuente

El archivo `2026.jsonl.gz` es JSON Lines comprimido con gzip.

- `.jsonl`: cada linea es un JSON independiente.
- `.gz`: compresion gzip.
- Se conserva como evidencia cruda.
- El checksum se guarda en `source_records.checksum`.
- La ruta se guarda en `source_records.raw_path`.

## 3. Carga local

```bash
curl -L -o data/raw/ocds/2026.jsonl.gz \
  "https://data.open-contracting.org/es/publication/135/download?name=2026.jsonl.gz"

uv run --directory apps/scrapers agenteperry sources collect ocds_peru \
  --input /home/miguel/projects/hacklatam/data/raw/ocds/2026.jsonl.gz \
  --out /home/miguel/projects/hacklatam/data/derived/ocds/contracts_2026.jsonl

uv run --directory apps/scrapers agenteperry graph map-records \
  /home/miguel/projects/hacklatam/data/derived/ocds/contracts_2026.jsonl \
  --out /home/miguel/projects/hacklatam/data/derived/ocds/graph_2026.jsonl

DATABASE_URL="postgresql://contralatam:dev_password@localhost:5432/contralatam" \
uv run --directory apps/scrapers agenteperry db sync \
  /home/miguel/projects/hacklatam/data/derived/ocds/contracts_2026.jsonl \
  --graph /home/miguel/projects/hacklatam/data/derived/ocds/graph_2026.jsonl

DATABASE_URL="postgresql://contralatam:dev_password@localhost:5432/contralatam" \
uv run --directory apps/scrapers agenteperry db chunk-contracts --source-code ocds_peru
```

## 4. Subida a Supabase Cloud

Usa el connection string directo de Supabase Postgres como `DATABASE_URL`.

```bash
export DATABASE_URL="postgresql://postgres.<project-ref>:<password>@aws-...supabase.com:6543/postgres?sslmode=require"
export DATABASE_SSL=true
```

Luego aplica migraciones en orden:

```bash
psql "$DATABASE_URL" -f packages/db/migrations/0001_extensions.sql
psql "$DATABASE_URL" -f packages/db/migrations/0002_tdr_core.sql
psql "$DATABASE_URL" -f packages/db/migrations/0003_source_registry.sql
psql "$DATABASE_URL" -f packages/db/migrations/0003_tdr_search_functions.sql
```

Despues sincroniza la data:

```bash
uv run --directory apps/scrapers agenteperry db sync \
  data/derived/ocds/contracts_2026.jsonl \
  --graph data/derived/ocds/graph_2026.jsonl \
  --batch-size 500

uv run --directory apps/scrapers agenteperry db chunk-contracts \
  --source-code ocds_peru \
  --batch-size 500
```

## 5. Auditoria SQL minima

```sql
SELECT COUNT(*) FROM source_records;
SELECT COUNT(*), COUNT(DISTINCT external_id) FROM source_records;

SELECT
  COUNT(*) FILTER (WHERE supplier_name IS NULL) AS sin_proveedor,
  COUNT(*) FILTER (WHERE monto IS NULL) AS sin_monto,
  COUNT(*) FILTER (WHERE fecha IS NULL) AS sin_fecha,
  COUNT(*) FILTER (WHERE checksum IS NULL) AS sin_checksum,
  COUNT(*) FILTER (WHERE raw_path IS NULL) AS sin_raw_path,
  COUNT(*) AS total
FROM source_records;

SELECT source_type, COUNT(*)
FROM document_chunks
GROUP BY source_type;
```

## 6. App web

Configura `apps/web/.env.local` para local:

```bash
DATABASE_URL=postgresql://contralatam:dev_password@localhost:5432/contralatam
DATABASE_SSL=false
```

Para Supabase:

```bash
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-...supabase.com:6543/postgres?sslmode=require
DATABASE_SSL=true
```

Ejecuta:

```bash
npm run dev
```

Rutas:

- `/contracts`: explorador de contratos OCDS.
- `/contracts/[externalId]`: detalle, metadata, raw JSON y relaciones.
- `/api/contracts`: API paginada.
- `/api/contracts/audit`: resumen de auditoria.
- `/api/contracts/[externalId]`: detalle JSON completo.

## 7. Metadata preservada

Cada contrato conserva:

- `external_id`: identificador publico.
- `source_code`: fuente, por ejemplo `ocds_peru`.
- `raw_data`: JSON oficial completo.
- `parsed_data`: campos normalizados.
- `checksum`: hash SHA-256 del archivo fuente.
- `raw_path`: ruta local del archivo crudo usado.
- `fetched_at`: timestamp de captura.
- `evidence_quote`: resumen humano legal-safe.
- `entity_name`, `supplier_name`, `monto`, `fecha`: campos de analisis.

## 8. Chunks narrativos

No se embebe el JSON crudo completo. Se genera un texto corto por contrato:

```text
Contrato publico OCDS: <external_id>.
Entidad contratante: <entity_name>.
Proveedor adjudicado: <supplier_name>.
Monto adjudicado: PEN <monto>.
Fecha registrada: <fecha>.
Tipo de procedimiento: <procedure_type>.
Evidencia normalizada: <evidence_quote>
```

Esto queda en `document_chunks` con metadata JSONB para busqueda, auditoria y futuros embeddings.
