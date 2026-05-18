# TASKS — SPEC-0008 SUNAT Padrón Enrichment

> Reactivado desde `specs/deferred/SPEC-0002-sunat-padron-collector`.  
> Alcance actual: enrichment no destructivo de `source_entities.company` + audit.

---

## Pre-implementación

- [ ] T-01 — Spec aprobado y mergeado a main [@miguel] [0.5h]
- [ ] T-02 — Branch `feat/SPEC-0008-sunat-padron-enrichment` desde main [@anthony] [0.1h]

## Implementación

### Collector hardening

- [ ] T-10 — Validar RUC 11 dígitos en `collectors/sunat.py` (`_normalize_ruc` vs `_digits_only`) [@anthony] [0.5h]
- [ ] T-11 — Agregar `source_url=SUNAT_PADRON_URL` al `CollectionResult` [@anthony] [0.2h]
- [ ] T-12 — Fixture `tests/fixtures/sunat_padron_sample.txt` con 20–50 filas reales (RUCs de OCDS si posible) [@anthony] [0.5h]
- [ ] T-13 — Test de parsing: `test_sunat_padron_parser_ruc_validation()` [@anthony] [0.5h]
- [ ] T-14 — Test de encoding: `test_sunat_padron_parser_encoding_n_tilde()` [@anthony] [0.3h]

### Enrichment no destructivo

- [ ] T-20 — Implementar `enrich_companies_from_sunat(records_jsonl, batch_size)` en `sync/loader.py` [@anthony] [1.5h]
  - Leer source_records SUNAT con RUC válido
  - Hacer match `canonical_id` contra `source_entities.company`
  - Preservar `display_name` OCDS
  - Merge metadata: `ocds_name`, `sunat_razon_social`, `sunat_estado`, `sunat_condicion`, `sunat_ubigeo`, `sunat_domicilio_fiscal`, `sunat_last_seen_at`
  - Merge `sources` array (agregar `sunat_padron` sin duplicar)
  - Retornar métricas: `companies_created`, `companies_enriched`, `errors`
- [ ] T-21 — Hook enrichment en `cli.py::sources_pipeline` para `source_code == "sunat_padron"` [@anthony] [0.5h]
- [ ] T-22 — Test `test_sunat_enrichment_preserves_ocds_name()` — obligatorio, no negociable [@anthony] [0.5h]
- [ ] T-23 — Test `test_sunat_enrichment_merges_metadata()` [@anthony] [0.5h]

### Audit SUNAT

- [ ] T-30 — Implementar `_build_sunat_audit()` con métricas específicas [@anthony] [0.5h]
  - total_records, with_valid_ruc, with_name, with_estado, with_condicion, with_ubigeo
  - companies_created, companies_enriched
  - ocds_companies_total, ocds_companies_with_ruc, ocds_companies_matched_sunat, ocds_match_rate
  - active_count, no_habido_count, baja_count
  - errors list
- [ ] T-31 — Guardar `audit.json` en `data/raw/sunat_padron/audit.json` [@anthony] [0.2h]
- [ ] T-32 — Tests de audit SUNAT [@anthony] [0.5h]

## Tests de integración

- [ ] T-40 — `pytest tests/` pasa completo (no romper OCDS ni TDR) [@anthony] [0.5h]
- [ ] T-41 — `ruff check src tests` 0 errores [@anthony] [0.2h]
- [ ] T-42 — `pyright src` 0 errores [@anthony] [0.2h]

## Documentación

- [ ] T-50 — Actualizar `docs/SCRAPING_ROADMAP.md`:
  - estado real de SUNAT;
  - métricas de corrida;
  - match rate contra OCDS;
  - problemas conocidos;
  - siguiente paso recomendado. [@anthony] [0.3h]
- [ ] T-51 — Agregar comando SUNAT a `apps/scrapers/README.md` (si existe sección de comandos) [@anthony] [0.2h]

## Cierre

- [ ] T-60 — Self-review diff completo [@anthony] [0.5h]
- [ ] T-61 — Run local end-to-end con `--limit 1000` o fixture [@anthony] [0.5h]
- [ ] T-62 — Ejecutar SQL de validación y verificar match rate [@anthony] [0.5h]
- [ ] T-63 — PR `feat(scrapers): close SUNAT padron enrichment audit (SPEC-0008)` [@anthony] [0.2h]
- [ ] T-64 — Aprobación @miguel [@miguel]
- [ ] T-65 — Squash + merge [@anthony]
- [ ] T-66 — Mover spec a `specs/completed/SPEC-0008-sunat-padron-enrichment/` [@anthony] [0.2h]

---

## Estimación

| Sección | Horas |
|---------|-------|
| Pre-implementación | 0.6 |
| Collector hardening | 2.0 |
| Enrichment no destructivo | 3.0 |
| Audit SUNAT | 1.2 |
| Tests de integración | 1.1 |
| Documentación | 0.5 |
| Cierre | 1.9 |
| **Total** | **~10h** |

Asignable a 1 dev en 1.5 días.

---

## Decisiones técnicas documentadas

1. **RUC 11 dígitos:** `_normalize_ruc()` rechaza RUCs incompletos (evita `co_` hash en enrichment).
2. **`source_code` no existe en `source_records`:** las queries SQL usan `JOIN source_catalog`.
3. **No reemplazar `display_name`:** `metadata.ocds_name` + `metadata.sunat_razon_social` coexisten.
4. **No `document_chunks` para SUNAT:** metadata estructurada, no RAG.
5. **Fixture obligatorio:** smoke test sin descargar 200MB ZIP.
6. **Comando correcto:** `cd apps/scrapers && uv run agenteperry sources pipeline sunat_padron --limit 1000`.
