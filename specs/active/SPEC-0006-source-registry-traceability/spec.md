# SPEC-0006: Source Registry Traceability

| Campo | Valor |
|-------|-------|
| **ID** | SPEC-0006 |
| **Estado** | in_progress |
| **Owner** | @miguel |
| **Reviewers** | TBD |
| **Sprint / Fase** | F5 |
| **Creado** | 2026-05-16 |
| **Ultima actualizacion** | 2026-05-16 |
| **Issue relacionado** | TBD |
| **PR de implementacion** | TBD |
| **Depende de** | SPEC-0005 |
| **Bloquea** | Demo de datos reales |

---

## 1. Problema

El pipeline ya puede colectar OCDS Peru y mapear contratos a entidades/relaciones, pero la data queda invisible para revision humana si solo existe en tablas internas. Para poder auditar y demostrar el valor del MVP, necesitamos ver contratos reales, su metadata, su fuente, su checksum, su grafo basico y sus chunks de busqueda sin perder trazabilidad.

---

## 2. Objetivo

Despues de este spec, el equipo podra explorar, auditar y chunkear data OCDS real con metadata suficiente para subirla a Supabase y mostrarla en una UI.

---

## 3. Contexto y restricciones

- Toca `source_records`, `source_entities`, `source_relationships`, `document_chunks` y la app web.
- Fuente principal: `ocds_peru` desde Open Contracting Data Registry.
- No acusa corrupcion ni genera conclusiones legales; solo muestra evidencia y senales de riesgo cuando existan reglas.
- No incluye ONPE, JNE, SUNARP, Neo4j, Graphiti ni ConflictMap full.
- La metadata cruda se mantiene en `raw_data` y `parsed_data` para trazabilidad.

---

## 4. Criterios de aceptacion

- [ ] API lista contratos con filtros por texto, fuente y paginacion.
- [ ] API detalle muestra contrato, metadata, raw JSON, parsed JSON y relaciones del grafo.
- [ ] API auditoria reporta conteos, faltantes, rangos de fecha y top montos.
- [ ] UI `/contracts` muestra data real y estado de auditoria.
- [ ] UI `/contracts/[externalId]` muestra trazabilidad completa del contrato.
- [ ] CLI puede generar chunks narrativos desde `source_records` hacia `document_chunks`.
- [ ] Tests, ruff, pyright, eslint y typecheck pasan.

---

## 5. Out of scope

- ONPE/JNE/SUNARP: requieren spec activa separada.
- Scoring automatico de corrupcion: legalmente fuera de alcance MVP.
- Neo4j/Graphiti: deferred.
- Embeddings pagados masivos: se prepara estructura, pero no se ejecuta gasto sin aprobacion.

---

## 6. Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|--------------|---------|------------|
| Carga masiva lenta en Supabase | media | media | Batch size configurable y auditoria por conteos |
| Metadata incompleta | media | alta | Campos `raw_data`, `parsed_data`, `checksum`, `raw_path`, `fetched_at` visibles |
| API local vs Supabase Cloud | media | media | Usar `DATABASE_URL` compatible con Postgres/Supabase |
| JSON crudo pesado en detalle | media | baja | Mostrarlo bajo `<details>` y limitar listas |

---

## 7. Metricas de exito

- 72k+ `source_records` explorables desde UI.
- 30k+ entidades visibles via resumen de auditoria.
- Contrato individual muestra evidencia, fuente, checksum y raw JSON.
- Chunks generados en `document_chunks` para al menos contratos OCDS.

---

## 8. Decisiones rechazadas

- No convertir OCDS completo a `tdr_documents`: OCDS no es PDF/TDR, requiere modelo generico.
- No embeber todo `raw_data`: es ruidoso y caro; se generan chunks narrativos.
- No ocultar metadata: trazabilidad es clave para auditoria.
