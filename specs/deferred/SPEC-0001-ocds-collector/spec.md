# SPEC-0001: OCDS Perú collector

| Campo | Valor |
|-------|-------|
| **ID** | SPEC-0001 |
| **Estado** | approved |
| **Owner** | @TBD-2 (Data Engineer) |
| **Reviewers** | @MiguelAAR10 |
| **Sprint / Fase** | F1 — Bootstrap |
| **Creado** | 2026-05-14 |
| **Última actualización** | 2026-05-14 |
| **Issue relacionado** | TBD |
| **PR de implementación** | TBD |
| **Depende de** | — |
| **Bloquea** | SPEC-0003 (scorer necesita contratos cargados) |

---

## 1. Problema

Sin datos de OCDS Perú cargados en la DB no podemos calcular ningún indicador FUNES. El padrón SUNAT solo identifica empresas; sin contratos no hay riesgo a detectar. Hoy `SELECT count(*) FROM contracts` = 0.

## 2. Objetivo

> Después de este spec, el sistema puede cargar todos los contratos públicos OCDS de Perú 2024–2026 en la tabla `contracts` con UPSERT idempotente, y crear las entities `company` y `public_entity` correspondientes.

## 3. Contexto y restricciones

- Fuente oficial: `https://data.open-contracting.org/es/publication/135`
- Formato: JSONL.gz (~77MB para 2026, 170MB para 2025, 147MB para 2024) — total ~400MB comprimido.
- Sin auth, sin captcha — descarga directa.
- Estándar OCDS: https://standard.open-contracting.org/latest/es/
- OCID prefix Perú: `ocds-dgv273-*`
- Investigación previa: [`hackl@latam/scraping_config.yaml § ocds_peru`](../../../hackl@latam/scraping_config.yaml)

**Restricciones:**
- Streaming obligatorio (no cargar 2GB en RAM)
- Idempotente: re-correr no duplica
- Una sola transacción por release falla atómicamente

## 4. Criterios de aceptación

- [ ] `uv run contralatam bootstrap-ocds --years 2024 2025 2026` corre end-to-end sin OOM
- [ ] `SELECT count(*) FROM contracts WHERE source_year IN (2024, 2025, 2026)` > 400,000
- [ ] `SELECT count(*) FROM entities WHERE entity_type = 'public_entity'` > 2,000
- [ ] `SELECT count(*) FROM entities WHERE entity_type = 'company' AND 'OCDS' = ANY(sources)` > 50,000
- [ ] `SELECT count(*) FROM relationships WHERE rel_type = 'GANO_CONTRATO'` > 200,000
- [ ] Re-correr el comando NO incrementa los counts (idempotencia)
- [ ] Test `test_ocds_collector.py` pasa con fixture VCR.py de 10 releases
- [ ] Logging estructurado: cada batch loggea `record_count` + `duration_ms`

## 5. Out of scope

- ❌ Backfill 2003–2023 — separado en SPEC futuro (volumen 2GB)
- ❌ Updates incrementales día a día — F2+, usaremos descarga mensual
- ❌ Postores perdedores (SEACE) — SPEC-0006 cuando se implemente
- ❌ Parsing de `parties[]` con roles complejos — solo buyer + suppliers en F1

## 6. Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Servidor OCDS cae durante descarga | baja | media | Resume via `Range` header + sha256 check |
| Schema OCDS cambia en update mensual | baja | alta | Pydantic validation + alerta en CI si falla parse |
| RAM se dispara | media | alta | `ijson` streaming + batch UPSERT de 500 |
| RUC inválido en payload | media | baja | `pe-sunat` valida check digit, sino se loggea y skip |

## 7. Métricas de éxito

- Tiempo total carga 3 años: < 30 min en máquina con 4 cores 8GB RAM
- RAM peak: < 1GB
- Duplicates después de 2 corridas: 0

## 8. Decisiones rechazadas

- ❌ Cargar todo OCDS global, no solo Perú — fuera de scope, hackathon focus PE
- ❌ Usar `pd.read_json` directo — explota RAM en 2GB JSONL
- ❌ Usar SQLAlchemy ORM para inserts — asyncpg COPY o `executemany` es 10x más rápido

## 9. Anexos

- [OCDS Perú dataset](https://data.open-contracting.org/es/publication/135)
- [OCDS release schema](https://standard.open-contracting.org/latest/es/schema/release/)
- [`hackl@latam/scraping_config.yaml`](../../../hackl@latam/scraping_config.yaml) líneas 17-100
- [`hackl@latam/CLAUDE.md`](../../../hackl@latam/CLAUDE.md) § "MÓDULO OCDS"
