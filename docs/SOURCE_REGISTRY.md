# Source Registry — Catálogo Y Trazabilidad

## Qué Es

Registro único de todas las fuentes de datos del proyecto. Cada fuente tiene metadata técnica, legal y operativa.

## Tabla: source_catalog

| Campo | Descripción |
|-------|-------------|
| `source_code` | ID único (snake_case) |
| `source_name` | Nombre legible |
| `source_url` | URL oficial |
| `source_type` | api / bulk_download / playwright / form_scraping / ckan / manual / reference |
| `priority` | P0 / P1 / P2 / P3 |
| `status` | planned / active / paused / deprecated |
| `license_note` | CC BY 4.0, TOS, etc. |
| `update_freq` | monthly / weekly / on_demand |
| `owner` | Quién la implementa |
| `method_notes` | Cómo se scrapea |

## Tabla: source_records

Registro genérico de cualquier fuente. JSONB flexible.

| Campo | Descripción |
|-------|-------------|
| `source_id` | FK a source_catalog |
| `external_id` | ID del sistema origen |
| `record_type` | contract / person / company / norm / etc. |
| `raw_data` | JSONB completo del origen |
| `parsed_data` | JSONB limpio |
| `checksum` | SHA256 |
| `fetched_at` | Timestamp |
| `retrieved_by` | Script + versión |
| `raw_path` | Ruta al archivo crudo |
| `entity_ruc` | RUC entidad |
| `supplier_ruc` | RUC proveedor |
| `monto` | Monto numérico |
| `fecha` | Fecha del registro |
| `page_number` | Página si aplica |
| `evidence_quote` | Cita textual |

## Trazabilidad Completa

Para cada dato podemos responder:

1. ¿De qué fuente viene? → `source_catalog.source_name`
2. ¿Cuándo se capturó? → `source_records.fetched_at`
3. ¿Qué script lo capturó? → `source_records.retrieved_by`
4. ¿Cuál era la URL? → `source_catalog.source_url`
5. ¿Qué archivo exacto? → `source_records.raw_path`
6. ¿Qué página contiene la evidencia? → `source_records.page_number`
7. ¿Qué cita textual? → `source_records.evidence_quote`
8. ¿Cuál es el checksum? → `source_records.checksum`

## Fuentes Sembradas

La migration `0003_source_registry.sql` ya inserta las 24 fuentes del legacy.

## Cómo Agregar Una Nueva Fuente

```sql
INSERT INTO source_catalog (source_code, source_name, source_url, source_type, priority, status, owner, method_notes)
VALUES ('mi_fuente', 'Mi Fuente', 'https://...', 'api', 'P1', 'planned', 'Miguel', 'Descripción del método');
```

## Reglas

1. Ningún registro sin `source_id`.
2. Ningún registro sin `fetched_at`.
3. Ningún registro sin `retrieved_by`.
4. Data cruda va a `data/` (ignorado por Git), metadata va a Supabase.
5. Checksum obligatorio para archivos descargados.
