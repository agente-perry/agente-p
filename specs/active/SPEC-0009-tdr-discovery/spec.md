# SPEC-0009: TDR Discovery — Salud + Ambiente/Minería

| Campo | Valor |
|-------|-------|
| **ID** | SPEC-0009 |
| **Estado** | active |
| **Owner** | Anthony |
| **Reviewers** | @miguel |
| **Sprint / Fase** | F7 — TDR Discovery |
| **Creado** | 2026-05-16 |
| **Depende de** | SPEC-0006 (OCDS pipeline cerrado) |
| **Bloquea** | SPEC-0010 (TDR Downloader v1) |

---

## 1. Problema

El motor documental de AgentePerry (parseo PDF, chunking, embeddings, flags) está listo pero no tiene TDRs reales para procesar:

- `tdr_documents` = 0
- `tdr_pages` = 0
- `tdr_chunks` = 0
- `tdr_flags` = 0

No sabemos:
- Cuántos contratos de sectores priorizados existen en OCDS 2024–2025
- Si esos contratos tienen TDRs/bases disponibles públicamente
- Dónde están alojados esos documentos
- Qué mecanismo de descarga requieren

## 2. Objetivo

> Mapear contratos OCDS 2024–2025 de sectores Salud y Ambiente/Minería, verificar disponibilidad de TDRs/bases, y descargar manualmente 1–3 ejemplos para validar el motor documental.

## 3. Criterios de aceptación

- [x] Query SQL filtra contratos Salud 2024–2025 por `entity_name` keywords
- [x] Query SQL filtra contratos Ambiente/Minería 2024–2025 por `entity_name` keywords
- [x] `data/filtered/salud_2024_2025.jsonl` generado con ≥ 2,000 contratos
- [x] `data/filtered/ambiente_2024_2025.jsonl` generado con ≥ 50 contratos
- [x] `data/filtered/summary.json` con conteos, top 20 entidades y proveedores
- [x] `data/tdr_recon/recon_20_processes.csv` con 10 Salud + 10 Ambiente
- [x] 1–3 TDRs reales descargados manualmente sin scraping masivo
- [x] URLs de documentos extraídas de `raw_data->tender->documents` verificadas
- [x] Reporte `docs/TDR_DISCOVERY_REPORT.md` con metodología, conteos, muestra, hallazgos, riesgos, recomendación para TDR Downloader v1
- [x] `docs/SCRAPING_ROADMAP.md` actualizado con prioridad TDR Discovery
- [x] 0 ruff, 0 pyright, tests pasan

## 4. Contexto técnico

- Base: `source_records` Postgres (OCDS Perú 2026)
- Campos utilizados: `record_type`, `fecha`, `entity_name`, `raw_data->tender->documents[].url`
- URLs SEACE: `https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode=<UUID>`
- Sin login, captcha ni paywall observado
- Formatos encontrados: PDF v1.3/v1.7, RAR (Win32 v4)

## 5. Out of scope

- ❌ Scraping masivo de SEACE (solo manual 1–3)
- ❌ Implementar TDR Downloader v1 (SPEC-0010)
- ❌ Parsear PDFs descargados en motor documental
- ❌ SUNAT enrichment (pausado temporalmente)
- ❌ SEACE/OECE pipeline masivo
- ❌ Frontend, dashboard, ConflictMap

## 6. Decisiones técnicas

| Decisión | Justificación |
|----------|---------------|
| **Filtrar por `entity_name` no `sector` formal** | OCDS no tiene campo sector estandarizado; keywords en `buyer.name` es práctico |
| **Muestra 20 procesos (10+10)** | Suficiente para recon de disponibilidad sin descarga masiva |
| **URLs de `tender.documents`** | OCDS incluye documentos de SEACE nativamente; no requiere scraping extra |
| **Descarga manual con `curl`** | Valida que URLs funcionan sin login; no es scraping masivo |
| **Priorizar Salud > Ambiente** | Mayor monto y cantidad; ESSALUD concentra 40% de contratos Salud |

## 7. Hallazgos clave

- 2,566 contratos Salud 2024–2025 (S/ 3.94B total)
- 99 contratos Ambiente/Minería 2024–2025 (S/ 58.7M total)
- 100% de muestra (20/20) tiene TDR/bases disponible vía URL directa SEACE
- 0 bloqueos (login/captcha/paywall) detectados
- Documentos múltiples por proceso: 4–28 docs (bases, pliegos, resúmenes)

## 8. Comando de ejecución

```bash
cd apps/scrapers
export DATABASE_URL=postgresql://contralatam:dev_password@localhost:5432/contralatam
uv run python src/agenteperry/discovery/tdr_discovery.py
```

## 9. Branch esperada

```
feat/SPEC-0009-tdr-discovery-salud-ambiente
```

## 10. Commit sugerido

```
feat(scrapers): discover TDR availability for priority sectors (SPEC-0009)
```
