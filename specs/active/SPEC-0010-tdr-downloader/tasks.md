# TASKS — SPEC-0010 TDR Downloader v1

> Implementar downloader controlado para TDRs/bases de contratos OCDS.  
> No parsear PDFs todavía. Solo descargar + registrar metadata.

---

## Pre-implementación

- [ ] T-01 — Spec aprobado y en `specs/active/` [@miguel] [0.2h]
- [ ] T-02 — Branch `feat/SPEC-0010-tdr-downloader-v1` desde main [@anthony] [0.1h]
- [ ] T-03 — Verificar schema `tdr_documents`: columnas `source_record_id`, `monto`, `document_type`, `download_error` — si faltan, crear migración `0004` [@anthony] [0.5h]
- [ ] T-04 — Verificar `.gitignore` cubre `data/tdrs/` (@anthony) [0.1h]

## Implementación

### Módulo downloader

- [ ] T-10 — Crear `apps/scrapers/src/agenteperry/tdr/downloader.py` con clase `TdrDownloader` [@anthony] [2h]
  - `__init__(self, db: DbClient, download_dir: Path, rate_limit_s: float = 1.0, max_retries: int = 3, max_docs_per_contract: int = 3)`
  - `fetch_documents(sector: str, since: date, limit: int | None, input_path: Path | None) -> list[DocCandidate]`
  - `score_document(doc_title: str) -> int` — score-based priority (TDR=100, bases integradas=80, pliego=60, ...)
  - `download_one(candidate: DocCandidate) -> DownloadResult`
  - `run(sector: str, since: date, limit: int | None, input_path: Path | None, dry_run: bool) -> DownloadAudit`
- [ ] T-11 — Modelo `DocCandidate` (ocid, sector, entity_name, monto, fecha, doc_title, doc_url, doc_format, source_record_id) [@anthony] [0.3h]
- [ ] T-12 — Modelo `DownloadResult` (candidate, status, file_path, checksum, error, content_type, size_bytes) [@anthony] [0.3h]
- [ ] T-13 — `_sanitize_filename(title: str, url: str) -> str` (snake_case, max 80 chars, agrega extensión de Content-Type) [@anthony] [0.5h]
- [ ] T-14 — `_download_with_retry(url: str, dest: Path) -> tuple[str, str, int]` (returns checksum, content_type, size_bytes) — usa `urllib.request`, NO `requests` [@anthony] [1h]
  - Rate limit: `time.sleep(rate_limit_s)` entre descargas
  - Retry: 3×, backoff `1s, 4s, 9s`
  - Validar Content-Type permitido
  - SHA256 checksum al vuelo (streaming)
- [ ] T-15 — `_upsert_tdr_document(result: DownloadResult) -> None` — upsert en `tdr_documents` [@anthony] [0.5h]

### Filtro de documentos

- [ ] T-20 — `fetch_from_db(db, sector, since, limit) -> list[DocCandidate]` — query SQL a `source_records` + `jsonb_array_elements(raw_data->'tender'->'documents')` [@anthony] [0.5h]
- [ ] T-21 — `fetch_from_jsonl(path: Path, sector: str, limit: int | None) -> list[DocCandidate]` — leer JSONL de Activity 3 [@anthony] [0.5h]
- [ ] T-22 — `filter_and_score(candidates: list[DocCandidate], max_per_contract: int) -> list[DocCandidate]` — score por título, dedup por `ocid`, top `max_per_contract` por contrato [@anthony] [0.5h]

### Audit

- [ ] T-30 — `DownloadAudit` model: total_candidates, downloaded, failed, not_found, duplicates, skipped, total_bytes, errors [@anthony] [0.3h]
- [ ] T-31 — Guardar `data/tdrs/audit_<sector>_<yyyymmdd_hhmmss>.json` [@anthony] [0.2h]

### CLI

- [ ] T-40 — Agregar `agenteperry tdr download` en `cli.py` [@anthony] [0.5h]
  ```
  agenteperry tdr download --sector salud --limit 10 [--input PATH] [--dry-run] [--max-docs N]
  ```
  - `--sector`: `salud` | `ambiente` (requerido)
  - `--limit`: int opcional
  - `--input`: JSONL de Activity 3 opcional (usa DB si no se provee)
  - `--dry-run`: solo mostrar candidatos, no descargar
  - `--max-docs`: max documentos por contrato (default: 3)
  - Steps: 1. Fetch candidates → 2. Score+filter → 3. Download → 4. Upsert tdr_documents → 5. Audit

### Migración (solo si necesaria)

- [ ] T-50 — Crear `packages/db/migrations/0004_tdr_documents_downloader.sql` si faltan columnas en `tdr_documents`:
  ```sql
  ALTER TABLE tdr_documents
    ADD COLUMN IF NOT EXISTS source_record_id uuid REFERENCES source_records(id),
    ADD COLUMN IF NOT EXISTS monto numeric,
    ADD COLUMN IF NOT EXISTS document_type text DEFAULT 'bases',
    ADD COLUMN IF NOT EXISTS download_error text,
    ADD COLUMN IF NOT EXISTS downloaded_at timestamptz;
  ```

## Tests

- [ ] T-60 — `tests/test_tdr_downloader.py` [@anthony] [1.5h]
  - `test_score_document_tdr_is_100()`: "Términos de Referencia" → 100
  - `test_score_document_bases_integradas_is_80()`: "Bases Integradas" → 80
  - `test_score_document_pliego_is_60()`: "Pliego de absolución" → 60
  - `test_score_document_default_is_10()`: "Oferta técnica" → 10
  - `test_sanitize_filename_no_special_chars()`: "Bases Administrativas" → `bases_administrativas.pdf`
  - `test_sanitize_filename_max_length()`: > 80 chars → truncado
  - `test_filter_and_score_picks_top_per_contract()`: 3 docs por contrato max
  - `test_filter_and_score_deduplicates_by_ocid()`: mismo ocid → un candidato
  - `test_download_one_dry_run_no_http_call()`: dry_run=True → no descarga
  - `test_download_one_mocked_success()`: monkeypatch urllib → DownloadResult.status == "downloaded"
  - `test_download_one_mocked_404()`: HTTP 404 → DownloadResult.status == "not_found"
  - `test_download_one_unsupported_format()`: Content-Type text/html → "unsupported_format"

## Validación e2e (manual, no en CI)

- [ ] T-70 — Correr `agenteperry tdr download --sector salud --limit 5 --dry-run` [@anthony] [0.2h]
- [ ] T-71 — Correr `agenteperry tdr download --sector salud --limit 5 --max-docs 2` [@anthony] [0.5h]
- [ ] T-72 — Verificar `tdr_documents` en DB [@anthony] [0.2h]
  ```sql
  select download_status, count(*), sum(estimated_value)
  from tdr_documents
  group by download_status;
  ```
- [ ] T-73 — Correr `agenteperry tdr download --sector ambiente --limit 5 --max-docs 2` [@anthony] [0.3h]
- [ ] T-74 — Verificar `data/tdrs/salud/` y `data/tdrs/ambiente/` [@anthony] [0.1h]

## Calidad

- [ ] T-80 — `uv run --extra dev pytest tests/test_tdr_downloader.py` pasa [@anthony] [0.2h]
- [ ] T-81 — `uv run --extra dev ruff check src tests` 0 errores [@anthony] [0.1h]
- [ ] T-82 — `uv run --extra dev pyright` 0 errores [@anthony] [0.1h]

## Documentación

- [ ] T-90 — Actualizar `docs/TDR_DISCOVERY_REPORT.md` con métricas reales post-descarga [@anthony] [0.3h]
- [ ] T-91 — Actualizar `docs/SCRAPING_ROADMAP.md`: SPEC-0010 completado, próximo SPEC-0002 (TDR Parser) [@anthony] [0.2h]

## Cierre

- [ ] T-95 — Self-review diff completo [@anthony] [0.3h]
- [ ] T-96 — PR `feat(scrapers): implement TDR downloader v1 (SPEC-0010)` [@anthony] [0.2h]
- [ ] T-97 — Aprobación @miguel [@miguel]
- [ ] T-98 — Mover spec a `specs/completed/SPEC-0010-tdr-downloader/` [@anthony] [0.1h]

---

## Estimación

| Sección | Horas |
|---------|-------|
| Pre-implementación | 0.9 |
| Módulo downloader | 5.1 |
| Filtro de documentos | 1.5 |
| Audit | 0.5 |
| CLI | 0.5 |
| Migración | 0.5 |
| Tests | 1.5 |
| Validación e2e | 1.3 |
| Calidad | 0.4 |
| Documentación | 0.5 |
| Cierre | 0.6 |
| **Total estimado** | **~13h** |

1.5–2 días para 1 dev.

---

## Dependencias técnicas

- `urllib.request` (stdlib) — no agregar `requests`
- `hashlib` (stdlib) — SHA256
- `time` (stdlib) — rate limit
- `mimetypes` (stdlib) — extensión desde Content-Type
- `agenteperry.db.client.DbClient` — upsert tdr_documents
- `agenteperry.tdr.ingestion.calculate_sha256` — ya existe, reusar
