# SPEC-0002: SUNAT Padrón Reducido collector [LEGACY → REACTIVADO AS SPEC-0008]

> **⚠️ Este spec fue reactivado con ID SPEC-0008.**  
> El alcance evolucionó de "collector standalone" a "enrichment no destructivo de source_entities.company".  
> Ver documentación actual: `specs/active/SPEC-0008-sunat-padron-enrichment/`

| Campo | Valor |
|-------|-------|
| **ID** | SPEC-0002 (LEGACY) → **SPEC-0008 (ACTIVO)** |
| **Estado** | **deferred → reactivated as SPEC-0008** |
| **Owner** | Anthony |
| **Reviewers** | @MiguelAAR10 |
| **Sprint / Fase** | F1 — Bootstrap |
| **Creado** | 2026-05-14 |
| **Última actualización** | 2026-05-14 |
| **Depende de** | — (paralelo a SPEC-0001) |
| **Bloquea** | SPEC-0003 (scorer necesita estado SUNAT de proveedores) |

---

## 1. Problema

OCDS expone RUC y nombre del proveedor, pero NO su estado SUNAT (HABIDO/NO HABIDO, ACTIVO/BAJA), ni el ubigeo del domicilio fiscal. Sin esto no podemos detectar:
- Proveedor NO HABIDO contratando
- Empresa de BAJA recibiendo contratos
- Domicilios compartidos (empresas fantasma)
- Antigüedad de la empresa al momento de convocatoria

## 2. Objetivo

> Después de este spec, el sistema tiene cargado el padrón reducido completo de SUNAT (14.5M+ contribuyentes) en `entities` con metadata que incluye estado tributario y ubigeo.

## 3. Contexto

- URL: `http://www2.sunat.gob.pe/padron_reducido_ruc.zip`
- Formato: ZIP → TXT pipe-delimited, encoding ISO-8859-1, ~200MB.
- 14.5M registros, sin auth, sin captcha.
- Actualización mensual.
- Investigación: [`hackl@latam/scraping_config.yaml § sunat_padron`](../../../hackl@latam/scraping_config.yaml)

## 4. Criterios de aceptación

- [ ] `uv run contralatam bootstrap-sunat` corre end-to-end sin OOM
- [ ] `SELECT count(*) FROM entities WHERE entity_type = 'company' AND 'SUNAT' = ANY(sources)` > 10,000,000
- [ ] `SELECT count(*) FROM entities WHERE metadata->>'condicion_domicilio' = 'NO HABIDO'` > 100,000
- [ ] Para empresa cruzada con OCDS: `SELECT metadata->>'condicion_domicilio', metadata->>'ubigeo' FROM entities WHERE canonical_id='20131312955'` retorna valores poblados
- [ ] Re-correr NO duplica (idempotencia)
- [ ] Test `test_padron_collector.py` con fixture pequeño pasa

## 5. Out of scope

- ❌ Padrón "local anexo" (otra URL) — opcional, SPEC futuro
- ❌ Consulta multi-RUC (formulario SUNAT) — SPEC-006X
- ❌ OAuth2 SOL (CPE) — no relevante para MVP
- ❌ Validación check digit en bulk — confiar en SUNAT
- ❌ Histórico de cambios mes a mes — solo último snapshot

## 6. Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Encoding extraño (no ISO-8859-1) | baja | alta | Detectar con `chardet` antes; fallback graceful |
| Fila con campos mal alineados | media | media | `on_bad_lines='skip'` + log; threshold 0.1% error |
| 14.5M filas explotan RAM | alta | alta | COPY via asyncpg, batches de 50k |
| URL SUNAT cambia | baja | alta | `sources.yaml` editable; hot-fix sin código |
| BD se llena de 14.5M filas | alta | media | Particionar `entities` por `entity_type`? Evaluar post-F1 |

## 7. Métricas de éxito

- Tiempo total: < 15 min en máquina dev
- RAM peak: < 2GB (con COPY streaming)
- Cruzar con OCDS: ≥ 70% de RUCs de proveedores OCDS están en padrón

## 8. Decisiones rechazadas

- ❌ Cargar padrón en tabla separada `sunat_padron` — preferimos unificar en `entities` con metadata JSONB
- ❌ Solo cargar RUCs que aparecen en OCDS — perdemos la capacidad de detectar empresas nuevas que aparecerán en contratos futuros
- ❌ ElasticSearch (Kembec) — overkill, `pg_trgm` + GIN suficiente

## 9. Anexos

- [SUNAT descarga padrón](https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html)
- [hackl@latam/scraping_config.yaml líneas 130-220](../../../hackl@latam/scraping_config.yaml)
- Repo Kembec consulta-peru: https://github.com/Kembec/consulta-peru
- Script jorgechavez6816/sunat_padron_ruc: https://github.com/jorgechavez6816/sunat_padron_ruc
