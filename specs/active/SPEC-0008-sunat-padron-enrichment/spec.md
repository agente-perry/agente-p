# SPEC-0008: SUNAT Padrón Enrichment

| Campo | Valor |
|-------|-------|
| **ID** | SPEC-0008 |
| **Origen** | Reactivado desde `specs/deferred/SPEC-0002-sunat-padron-collector` |
| **Estado** | active |
| **Owner** | Anthony |
| **Reviewers** | @miguel |
| **Sprint / Fase** | F6 — Enrichment |
| **Creado** | 2026-05-14 (original), 2026-05-16 (reactivado) |
| **Última actualización** | 2026-05-16 |
| **Depende de** | SPEC-0006 (source-registry-traceability: OCDS pipeline cerrado) |
| **Bloquea** | Activity 3 — SEACE/OECE prioritized categories |

---

## 1. Problema

OCDS Peru ya está cargado (72,399 records, 30,575 companies). De esas companies, solo **67.0% tienen RUC real** en `canonical_id`; las demás usan hash fallback `co_xxxx`. Además, OCDS no provee:

- Estado tributario SUNAT (ACTIVO / BAJA)
- Condición de domicilio (HABIDO / NO HABIDO)
- Ubigeo del domicilio fiscal
- Razón social oficial SUNAT (puede diferir de la registrada en OCDS)

Sin esto no podemos detectar señales de riesgo como:
- Proveedor NO HABIDO contratando
- Empresa de BAJA recibiendo contratos
- Domicilios compartidos (empresas fantasma)

## 2. Objetivo

> Cerrar `sunat_padron` como fuente P0 de **enriquecimiento** operativa, trazable y auditable.

Después de este spec:
- `source_records` contiene registros SUNAT con RUC, razón social, estado, condición, ubigeo.
- `source_entities.company` con RUC real está enriquecida con metadata SUNAT sin destruir nombres ni metadata OCDS.
- `audit.json` reporta match rate contra empresas OCDS.
- Fixture de 20–50 filas permite validar sin descargar 14.5M.

## 3. Contexto

- URL: `https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html`
- Formato: ZIP → TXT pipe-delimited, encoding ISO-8859-1, ~200 MB.
- 14.5M registros, sin auth, sin captcha.
- Actualización mensual.
- Collector ya existe: `apps/scrapers/src/agenteperry/collectors/sunat.py`.
- Pipeline existe: `agenteperry sources pipeline <source_code>`.
- **Comando de corrida:**
  ```bash
  cd apps/scrapers
  uv run agenteperry sources pipeline sunat_padron --limit 1000
  ```
- **Nota técnica:** `source_records` no tiene columna `source_code`; tiene `source_id` FK a `source_catalog`. Toda query de validación debe hacer `JOIN source_catalog`.

## 4. Criterios de aceptación

- [ ] `uv run agenteperry sources pipeline sunat_padron --limit 1000` corre end-to-end.
- [ ] `source_records` tiene registros `sunat_padron` (verificar vía `JOIN source_catalog`).
- [ ] `entity_ruc` tiene RUC válido de 11 dígitos en ≥ 99% de registros.
- [ ] `parsed_data` contiene `estado`, `condicion`, `ubigeo`, `domicilio_fiscal`.
- [ ] `source_entities.company` con RUC existente (de OCDS) se enriquece sin reemplazar `display_name`.
- [ ] `metadata.ocds_name` y `metadata.sunat_razon_social` coexisten cuando hay match.
- [ ] `metadata.sunat_estado`, `metadata.sunat_condicion`, `metadata.sunat_ubigeo`, `metadata.sunat_domicilio_fiscal`, `metadata.sunat_last_seen_at` poblados.
- [ ] `audit.json` generado con métricas: total_records, with_valid_ruc, with_name, with_estado, with_condicion, with_ubigeo, companies_created, companies_enriched, ocds_match_rate, active_count, no_habido_count, baja_count.
- [ ] Fixture `tests/fixtures/sunat_padron_sample.txt` con 20–50 filas reales permite smoke test sin descarga.
- [ ] Si descarga SUNAT falla o es muy pesada, se documenta bloqueo y se usa fixture para validar enrichment.
- [ ] Tests, ruff, pyright pasan.

## 5. Out of scope

- ❌ Cargar padrón completo de 14.5M (solo controlado / limitado por ahora).
- ❌ Padrón "local anexo" (otra URL) — SPEC futuro.
- ❌ Consulta multi-RUC (formulario SUNAT) — SPEC futuro.
- ❌ OAuth2 SOL (CPE) — no relevante para MVP.
- ❌ SEACE/OECE — Activity 3, solo después de cerrar SUNAT.
- ❌ Contraloría — SPEC futuro.
- ❌ TDR, UI, dashboard — no tocar.
- ❌ ONPE, JNE, SUNARP — deferred.
- ❌ Validación check digit en bulk — confiar en SUNAT.
- ❌ Histórico de cambios mes a mes — solo último snapshot.

## 6. Decisiones técnicas

| Decisión | Justificación |
|----------|---------------|
| **No reemplazar `display_name`** | OCDS ya tiene nombre de proveedor; SUNAT tiene razón social oficial. Ambos se guardan en `metadata`. |
| **`metadata.ocds_name` + `metadata.sunat_razon_social`** | Trazabilidad completa: sabemos qué nombre vino de qué fuente. |
| **`source_code` no existe en `source_records`** | Schema usa `source_id` FK. Las queries de validación necesitan `JOIN source_catalog`. |
| **Enrichment corre como paso adicional post-upsert** | `source_records` se insertan primero; luego se hace merge de metadata en `source_entities` ya existentes. |
| **Fixture para smoke test** | SUNAT ZIP es 200MB; no bloquear dev por descarga lenta. |
| **No crear `document_chunks` para SUNAT** | SUNAT es metadata estructurada, no texto narrativo para RAG. |

## 7. Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| SUNAT ZIP no descarga o URL cambió | media | alta | Usar fixture de 50 filas para validar pipeline. Documentar bloqueo. |
| 14.5M filas explotan RAM/time | alta | alta | Usar `--limit` en dev; full load solo en prod con monitoreo. |
| Encoding corrupto (no ISO-8859-1) | baja | alta | Fixture con `Ñ`, tildes para validar. Fallback UTF-8. |
| Fila con campos mal alineados | media | media | `on_bad_lines='skip'` + threshold 0.1% error. |
| BD se llena de 14.5M filas | alta | media | Evaluar partición `source_records` por `source_id` post-carga. |
| Enrichment sobrescribe metadata OCDS | media | alta | Test obligatorio: `_test_sunat_enrichment_preserves_ocds_name()`. |

## 8. Métricas de éxito

- Pipeline `--limit 1000` completo en < 2 min.
- Match rate OCDS companies con SUNAT: reportado en `audit.json`.
- ≥ 95% de registros SUNAT con RUC válido, estado y condición.
- 0 tests rotos, 0 ruff, 0 pyright.

## 9. Decisiones rechazadas

- ❌ Cargar padrón en tabla separada `sunat_padron` — unificamos en `source_records` + `source_entities`.
- ❌ Reemplazar `display_name` con razón social SUNAT — destruiría trazabilidad OCDS.
- ❌ Solo cargar RUCs que aparecen en OCDS — perdemos capacidad de detectar empresas nuevas.
- ❌ Asyncpg COPY streaming — el pipeline actual (JSONL + batch upsert) es suficiente para dev. Optimizar si full 14.5M lo requiere.
- ❌ ElasticSearch — `pg_trgm` + GIN suficiente.

## 10. Comando de corrida

```bash
cd apps/scrapers
export DATABASE_URL=postgresql://contralatam:dev_password@localhost:5432/contralatam

# Smoke test con fixture
uv run agenteperry sources pipeline sunat_padron \
  --input tests/fixtures/sunat_padron_sample.txt \
  --limit 20

# Controlado con descarga real
uv run agenteperry sources pipeline sunat_padron --limit 1000
```

## 11. SQL de validación

```sql
-- Registros SUNAT cargados
select count(*)
from source_records r
join source_catalog c on c.id = r.source_id
where c.source_code = 'sunat_padron';

-- Calidad básica SUNAT
select
  count(*) as total,
  count(*) filter (where r.entity_ruc ~ '^[0-9]{11}$') as with_valid_ruc,
  count(*) filter (where r.entity_name is not null and r.entity_name <> '') as with_name,
  count(*) filter (where r.parsed_data->>'estado' is not null) as with_estado,
  count(*) filter (where r.parsed_data->>'condicion' is not null) as with_condicion,
  count(*) filter (where r.parsed_data->>'ubigeo' is not null) as with_ubigeo
from source_records r
join source_catalog c on c.id = r.source_id
where c.source_code = 'sunat_padron';

-- Match OCDS companies contra SUNAT
select
  count(*) as ocds_companies_with_ruc,
  count(sunat.id) as matched_sunat,
  round(count(sunat.id)::numeric / nullif(count(*), 0) * 100, 2) as match_rate_pct
from source_entities ocds
left join source_records sunat on sunat.entity_ruc = ocds.canonical_id
left join source_catalog c on c.id = sunat.source_id and c.source_code = 'sunat_padron'
where ocds.entity_type = 'company'
  and ocds.canonical_id ~ '^[0-9]{11}$';

-- Distribución de estado SUNAT
select
  r.parsed_data->>'estado' as estado,
  count(*) as total
from source_records r
join source_catalog c on c.id = r.source_id
where c.source_code = 'sunat_padron'
group by r.parsed_data->>'estado'
order by total desc;

-- Distribución de condición SUNAT
select
  r.parsed_data->>'condicion' as condicion,
  count(*) as total
from source_records r
join source_catalog c on c.id = r.source_id
where c.source_code = 'sunat_padron'
group by r.parsed_data->>'condicion'
order by total desc;

-- Verificar enrichment no destructivo
select
  canonical_id,
  display_name,                       -- debe seguir siendo nombre OCDS
  metadata->>'ocds_name' as ocds_name,
  metadata->>'sunat_razon_social' as sunat_name,
  metadata->>'sunat_estado' as estado,
  metadata->>'sunat_condicion' as condicion
from source_entities
where entity_type = 'company'
  and metadata->>'sunat_estado' is not null
limit 5;
```

## 12. Branch esperada

```
feat/SPEC-0008-sunat-padron-enrichment
```

## 13. Commit sugerido

```
feat(scrapers): close SUNAT padron enrichment audit (SPEC-0008)
```

## 14. Anexos

- [SUNAT descarga padrón](https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html)
- Collector existente: `apps/scrapers/src/agenteperry/collectors/sunat.py`
- Pipeline existente: `apps/scrapers/src/agenteperry/cli.py::sources_pipeline`
- Schema: `packages/db/migrations/0003_source_registry.sql`
