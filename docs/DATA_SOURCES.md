# Catálogo de Fuentes — AgentePerry TDR Scanner

Este documento reemplaza al catálogo `Fuentes-Hack@Latam` como fuente de verdad operativa.

## Leyenda

| Prioridad | Significado |
|-----------|-------------|
| **P0 — MVP** | Fuente activa del sprint actual. Implementar ahora. |
| **P1 — Enrichment** | Fuente valiosa para post-MVP. Requiere spec activo. |
| **P2 — Post-MVP** | Fuente interesante pero fuera del foco inmediato. |
| **P3 — Diferido** | Fuente compleja o de bajo impacto inmediato. |

## Fuentes P0 — MVP

| Fuente | Formato | Método | Owner | Estado | Spec |
|--------|---------|--------|-------|--------|------|
| **OCDS Perú** | JSONL.gz / CSV | Bulk download | Anthony | planned | SPEC-0006 |
| **SUNAT Padrón** | ZIP → TXT | Bulk download | Anthony | planned | SPEC-0006 |
| **OECE/SEACE** | CSV / XLSX | Pentaho direct | John | planned | SPEC-0006 |
| **Contraloría Sanciones** | XLSX | Playwright | John | planned | SPEC-0006 |
| **Ley 32069** | PDF | Reference / RAG | Miguel | active | SPEC-0006 |
| **TDRs manuales** | PDF | Carga manual | John | active | SPEC-0001 |

## Fuentes P1 — Enrichment

| Fuente | Formato | Método | Owner |
|--------|---------|--------|-------|
| SUNAT Consulta múltiple RUC | HTML | Form + CAPTCHA | Anthony |
| CGR Informes de Control | JSON + PDF | Playwright XHR | John |
| MEF Transparencia Económica | Web/API | Scraping controlado | Anthony |
| MEF Datos Abiertos | CSV/JSON | CKAN API | Anthony |
| SIDJI DJI | HTML | Playwright on-demand | Miguel |
| ONPE Claridad | JSON | Playwright XHR | Noelia |
| JNE Voto Informado | JSON | Playwright XHR | Noelia |
| JNE Plataforma Electoral | JSON | Playwright XHR | Noelia |
| Congreso Legislación | HTML + PDF | ASP.NET scraping | Miguel |
| Congreso Proyectos | HTML + PDF | Controlled scraping | Miguel |
| Ojo Público FUNES | Web | Reference | John |
| Open Contracting Memoria | Web | Reference | Anthony |
| Convoca Contrataciones | HTML | Drupal 9 scraping | Noelia |

## Fuentes P2-P3 — Diferido

| Fuente | Formato | Método | Owner | Notas |
|--------|---------|--------|-------|-------|
| SUNARP Conoce Aquí | Web | Manual | John | Requiere DNI/partida |
| SUNARP SPRL | Web | Manual | John | Acceso pagado |
| SUNARP Personas Jurídicas | HTML | Controlled | John | 5 req/min |
| Poder Judicial | Web | Manual | Miguel | Solo sentencias firmes |
| Ministerio Público | Web | Manual | Miguel | Solo comunicados |
| Convoca Pandemia | Web | Semi-manual | Noelia | Enrichment por caso |

## Métodos De Scraping

Detalle técnico completo: [`docs/SCRAPING_TECHNIQUES.md`](SCRAPING_TECHNIQUES.md)

### Bulk Download (Fácil)
- OCDS Perú: JSONL.gz por año
- SUNAT Padrón: ZIP con TXT pipe-delimited
- MEF CKAN: API REST

### Playwright Controlado (Medio-Alto)
- Contraloría Sanciones: intercept download XLSX
- CGR Informes: intercept XHR JSON
- ONPE Claridad: intercept XHR
- JNE: intercept XHR Angular
- SIDJI: on-demand con CAPTCHA

### Form Scraping (Medio)
- Congreso: ASP.NET WebForms
- SUNARP PJ: form POST

### Manual / Reference
- Ley 32069: descarga PDF, indexar para RAG
- FUNES / Open Contracting: referencia metodológica
- Poder Judicial / MP: solo manual

## Patrones De Detección

8 patrones de riesgo con queries SQL:

1. Socio Invisible (conflicto familiar)
2. Aportante Favorito (retorno electoral)
3. Empresa Fantasma (creada para ganar)
4. Monopolio Silencioso (concentración)
5. Comité Cómplice (mismo evaluador)
6. Sancionado Activo (inhabilitado)
7. Ventana Corta (plazo excluyente)
8. Conflicto Declarado (DJI ignorada)

Ver [`docs/CONFLICT_OF_INTEREST.md`](CONFLICT_OF_INTEREST.md)

## Grafo En Postgres

Modelo de entidades y relaciones en PostgreSQL sin Neo4j:

- `source_entities` — nodos (persona, empresa, entidad)
- `source_relationships` — aristas (ganó contrato, representa a, aportó a)
- `get_subgraph()` — traversal recursivo

Ver [`docs/GRAPH_FOUNDATION.md`](GRAPH_FOUNDATION.md)

## RAG Foundation

- `document_chunks` — texto fragmentado
- `document_embeddings` — pgvector (1536 dims)
- Ley 32069, informes CGR, TDRs indexados
- Búsqueda semántica cruzada

## Metadata Trazable

Cada registro debe incluir:

```text
source_id, source_name, source_url, collection_method,
fetched_at, retrieved_by, checksum, external_id,
entity_ruc, entity_name, region, period_year,
page_number, evidence_quote, evidence_url
```

Ver [`docs/SOURCE_REGISTRY.md`](SOURCE_REGISTRY.md)

## Checklist De Validación

- [ ] Acceso público confirmado
- [ ] Formato identificado
- [ ] 3-5 registros de prueba obtenidos
- [ ] Campos mapeables a schema
- [ ] Proceso repetible sin duplicados
- [ ] TOS / licencia respetada
- [ ] Metadata trazable completa
- [ ] No commitear data cruda
