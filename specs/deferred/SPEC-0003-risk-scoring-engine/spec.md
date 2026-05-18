# SPEC-0003: Risk scoring engine (FUNES 7 indicadores)

| Campo | Valor |
|-------|-------|
| **ID** | SPEC-0003 |
| **Estado** | approved |
| **Owner** | @MiguelAAR10 (Backend) |
| **Reviewers** | @TBD-2 (Data) |
| **Sprint / Fase** | F2 — Scoring |
| **Creado** | 2026-05-14 |
| **Depende de** | SPEC-0001, SPEC-0002 (datos cargados) |
| **Bloquea** | SPEC-0004 (Amplifier necesita casos) |

---

## 1. Problema

Tenemos contratos y empresas cargados, pero no hay forma de saber cuáles merecen atención. Manualmente revisar 500k contratos es imposible. Necesitamos un algoritmo que asigne `risk_score ∈ [0, 1]` a cada contrato basado en señales objetivas.

## 2. Objetivo

> Después de este spec, todo contrato tiene `risk_score`, `nivel_riesgo` y lista de `risk_flags` calculados; los contratos con `score ≥ 0.5` se promueven a `risk_cases` listos para revisión humana.

## 3. Contexto

- Metodología: FUNES de Ojo Público (23 indicadores totales). Implementaremos 7 en MVP.
- Investigación: [`docs/METHODOLOGY.md`](../../../docs/METHODOLOGY.md) + [`hackl@latam/scraping_config.yaml § scoring`](../../../hackl@latam/scraping_config.yaml)
- Stub inicial: [`apps/scrapers/src/contralatam/scoring/indicators.py`](../../../apps/scrapers/src/contralatam/scoring/indicators.py)

### Indicadores en scope (7)

| ID | Fuente | Peso |
|----|--------|------|
| `unico_postor` | OCDS | 0.15 |
| `contratacion_directa` | OCDS | 0.12 |
| `delta_monto` | OCDS | 0.05 |
| `plazo_corto` | OCDS | 0.07 |
| `monto_atipico` | OCDS (P95 por método) | 0.05 |
| `no_habido` | SUNAT | 0.07 |
| `empresa_nueva` | SUNAT + OCDS | 0.08 |

## 4. Criterios de aceptación

- [ ] `uv run contralatam score --years 2024 2025 2026` corre en < 5 min para ~500k contratos
- [ ] Cada contrato en rango tiene fila en `risk_flags` por cada indicador que disparó
- [ ] `SELECT count(*) FROM risk_flags` > 50,000
- [ ] Distribución de scores razonable: ~70% BAJO, ~15% MEDIO, ~10% ALTO, ~5% CRITICO
- [ ] `uv run contralatam create-cases --min-score 0.5` crea filas en `risk_cases` para todo contrato con `score >= 0.5`
- [ ] `risk_cases.slug` único y human-readable: `<ubigeo>-<supplier-slug>-<ocid-short>`
- [ ] Re-correr el scoring con mismos datos produce mismos scores (determinista)
- [ ] Tests `test_indicators.py` y `test_scoring.py` verdes

## 5. Out of scope

- ❌ Los otros 16 indicadores (CGR, ONPE, JNE, DJI) — SPECs futuros
- ❌ Indicadores que requieren grafo (concentración, recurrencia, conexión política) — SPEC-0005
- ❌ ML probabilístico (modelo entrenado) — F5+
- ❌ UI para ver scores — SPEC-0007

## 6. Riesgos

| Riesgo | Mitigación |
|--------|------------|
| P95 por método requiere agregado costoso | Vista materializada `mv_monto_p95_por_method`, refresh mensual |
| `empresa_nueva` necesita `fecha_inicio_actividades` no en padrón reducido | Skip indicador si campo faltante, log warning, indicar en docs |
| Bonus de acumulación (>= 3 flags) infla scores artificialmente | Tuneable vía config; doc claro |

## 7. Métricas de éxito

- Top-20 casos críticos manualmente revisables (no falsos positivos absurdos)
- `score` de un contrato benchmark conocido (caso de prensa público) cae en ALTO+

## 8. Decisiones rechazadas

- ❌ Calcular scoring en SQL puro (CTE complejas) — Python permite tests unitarios + claridad
- ❌ Solo flags binarios sin score numérico — pierde granularidad para ranking
- ❌ Triggear scoring en cada INSERT — batch off-hours es más simple y eficiente
