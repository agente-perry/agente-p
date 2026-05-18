# Plan — AgentePerry TDR Scanner

## Sprint 0 — Limpieza y Foco

Objetivo: que cualquier persona entienda que el MVP es TDR Scanner.

Entregables:

- README reescrito.
- AGENTS y TEAM alineados.
- Specs activos TDR.
- Legacy diferido.
- Schema TDR minimo.
- Data hygiene documentada.

## Sprint 1 — Data Core

Objetivo: cargar 5-20 TDRs reales con metadata y texto por pagina.

Verificacion:

```sql
select count(*) from tdr_documents;
select count(*) from tdr_pages;
```

## Sprint 2 — Chunks + Embeddings

Objetivo: buscar semanticamente dentro de TDRs.

Smoke queries:

- formato A3
- entregables impresos
- certificacion ISO
- experiencia del postor
- camionetas
- plazo de entrega

## Sprint 3 — Flags

Objetivo: detectar senales iniciales con evidencia textual.

Verificacion:

```sql
select flag_code, evidence_quote, page_number from tdr_flags limit 20;
```

## Sprint 4 — API / Dossier Minimo

Objetivo: exponer `GET /api/tdr/{id}` con titulo, entidad, score, flags y preguntas de revision.
