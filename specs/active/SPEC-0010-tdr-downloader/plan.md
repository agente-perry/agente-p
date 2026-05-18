# PLAN — SPEC-0010 TDR Downloader v1

> Plan técnico de implementación. El spec está en `spec.md`, las tareas en `tasks.md`.

---

## 1. Arquitectura de módulos

```
apps/scrapers/src/agenteperry/
  tdr/
    downloader.py          ← NUEVO: TdrDownloader, DocCandidate, DownloadResult
    ingestion.py           ← existente, reusar calculate_sha256
    chunking.py            ← existente, no tocar
    embeddings.py          ← existente, no tocar
    flags.py               ← existente, no tocar
    index.py               ← agregar "tdr download" a índice CLI
    models.py              ← existente; agregar DownloadAudit si no hay conflicto
  discovery/
    tdr_discovery.py       ← existente (Activity 3), reusar como fuente de JSONL
  cli.py                   ← agregar subcomando "tdr download"
  db/
    client.py              ← sin cambios

packages/db/migrations/
  0004_tdr_documents_downloader.sql  ← NUEVO si faltan columnas
```

---

## 2. Flujo de datos completo

```
Input A: DB query
   source_records (record_type='contract', sector keywords)
   → jsonb_array_elements(raw_data->'tender'->'documents')
   → DocCandidate list

Input B: JSONL
   data/filtered/salud_2024_2025.jsonl (Activity 3)
   → DocCandidate list

         ▼
   score_document(title) → priority int
   filter_and_score(candidates, max_per_contract)
         ▼
   DocCandidate (sorted by score DESC, deduplicated by ocid)
         ▼
   TdrDownloader.download_one(candidate)
     └─ urllib.request.urlopen(url, timeout=60)
     └─ validate Content-Type
     └─ stream to disk + SHA256
     └─ time.sleep(rate_limit_s)
         ▼
   DownloadResult (status, file_path, checksum, size_bytes, content_type)
         ▼
   _upsert_tdr_document(result)
     └─ INSERT INTO tdr_documents ... ON CONFLICT (external_id) DO UPDATE
         ▼
   DownloadAudit
     └─ save to data/tdrs/audit_<sector>_<timestamp>.json
```

---

## 3. Estructura de `downloader.py`

```python
@dataclass
class DocCandidate:
    ocid: str
    sector: str
    entity_name: str | None
    monto: float | None
    fecha: date | None
    supplier_name: str | None
    supplier_ruc: str | None
    doc_title: str
    doc_url: str
    doc_format: str | None
    source_record_id: str | None  # UUID de source_records
    score: int = 0

@dataclass
class DownloadResult:
    candidate: DocCandidate
    status: str  # downloaded | failed | not_found | unsupported_format | duplicate | skipped
    file_path: Path | None
    checksum: str | None
    content_type: str | None
    size_bytes: int
    error: str | None

@dataclass
class DownloadAudit:
    sector: str
    run_at: str
    total_candidates: int
    downloaded: int
    failed: int
    not_found: int
    duplicates: int
    skipped: int
    total_bytes: int
    errors: list[str]

class TdrDownloader:
    def __init__(self, db: DbClient, download_dir: Path,
                 rate_limit_s: float = 1.0, max_retries: int = 3,
                 max_docs_per_contract: int = 3) -> None: ...

    def fetch_from_db(self, sector: str, since: date, limit: int | None) -> list[DocCandidate]: ...
    def fetch_from_jsonl(self, path: Path, sector: str, limit: int | None) -> list[DocCandidate]: ...
    def score_document(self, doc_title: str) -> int: ...
    def filter_and_score(self, candidates: list[DocCandidate]) -> list[DocCandidate]: ...
    def download_one(self, candidate: DocCandidate, dry_run: bool = False) -> DownloadResult: ...
    def run(self, sector: str, since: date, limit: int | None,
            input_path: Path | None, dry_run: bool) -> DownloadAudit: ...
```

---

## 4. Prioridad de documentos (score)

```python
DOC_SCORES: list[tuple[str, int]] = [
    ("tdr",                          100),
    ("términos de referencia",       100),
    ("terminos de referencia",       100),
    ("especificaciones técnicas",    90),
    ("especificaciones tecnicas",    90),
    ("especificacion tecnica",       90),
    ("bases integradas",             80),
    ("bases administrativas",        80),
    ("bases del proceso",            70),
    ("bases",                        50),
    ("pliego de absolución",         60),
    ("pliego de observaciones",      60),
    ("pliego",                       55),
    ("documentos de presentacion",   30),
    ("resumen ejecutivo",            20),
]
# Cualquier otro → 10
```

---

## 5. Sanitizado de nombres de archivo

```python
def _sanitize_filename(title: str, content_type: str, url: str) -> str:
    """
    "Bases Integradas" + application/pdf → "bases_integradas.pdf"
    Truncar a 80 chars (sin extensión).
    Extensión: derivada de Content-Type, fallback de URL, default ".bin".
    """
    import re
    name = title.lower().strip()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s-]+", "_", name)
    name = name[:80]
    ext = _ext_from_content_type(content_type) or _ext_from_url(url) or ".bin"
    return f"{name}{ext}"
```

---

## 6. Download con retry y rate limit

```python
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/zip",
    "application/rar",
    "application/x-rar-compressed",
    "application/vnd.rar",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/octet-stream",  # SEACE usa este para RAR/ZIP
}

def _download_with_retry(
    url: str, dest: Path, max_retries: int, rate_limit_s: float
) -> tuple[str, str, int]:
    """Returns (checksum_sha256, content_type, size_bytes)."""
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                content_type = resp.headers.get_content_type()
                if content_type not in ALLOWED_CONTENT_TYPES:
                    raise UnsupportedFormatError(content_type)
                h = hashlib.sha256()
                size = 0
                with dest.open("wb") as f:
                    while chunk := resp.read(65536):
                        f.write(chunk)
                        h.update(chunk)
                        size += len(chunk)
                return h.hexdigest(), content_type, size
        except UnsupportedFormatError:
            raise
        except OSError:
            if attempt < max_retries - 1:
                time.sleep((attempt + 1) ** 2)
            else:
                raise
        finally:
            time.sleep(rate_limit_s)
```

---

## 7. CLI `agenteperry tdr download`

El comando se integra en `cli.py` bajo el grupo `tdr`:

```python
@tdr_group.command("download")
@click.option("--sector", required=True, type=click.Choice(["salud", "ambiente"]))
@click.option("--limit", type=int, default=None)
@click.option("--input", "input_path", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--max-docs", type=int, default=3, show_default=True)
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--since", type=click.DateTime(formats=["%Y-%m-%d"]), default="2024-01-01")
@click.option("--download-dir", type=click.Path(path_type=Path), default=Path("data/tdrs"))
def tdr_download(sector, limit, input_path, max_docs, dry_run, since, download_dir):
    """Download TDR/bases documents from OCDS contracts."""
    from agenteperry.tdr.downloader import TdrDownloader
    from agenteperry.db.client import DbClient

    downloader = TdrDownloader(
        db=DbClient(),
        download_dir=download_dir,
        max_docs_per_contract=max_docs,
    )
    audit = downloader.run(
        sector=sector,
        since=since.date(),
        limit=limit,
        input_path=input_path,
        dry_run=dry_run,
    )
    # Display results with Rich table
    ...
```

---

## 8. Migración `0004_tdr_documents_downloader.sql`

Solo crear si las columnas no existen en `tdr_documents`:

```sql
-- Migration: add downloader-specific columns to tdr_documents
ALTER TABLE tdr_documents
  ADD COLUMN IF NOT EXISTS source_record_id   uuid REFERENCES source_records(id),
  ADD COLUMN IF NOT EXISTS monto              numeric,
  ADD COLUMN IF NOT EXISTS document_type      text DEFAULT 'bases',
  ADD COLUMN IF NOT EXISTS download_error     text,
  ADD COLUMN IF NOT EXISTS downloaded_at      timestamptz,
  ADD COLUMN IF NOT EXISTS supplier_name      text,
  ADD COLUMN IF NOT EXISTS supplier_ruc       text;

-- Index for fast lookup by sector + status
CREATE INDEX IF NOT EXISTS idx_tdr_documents_sector_status
  ON tdr_documents(sector, download_status);

-- Index for lookup by source_record
CREATE INDEX IF NOT EXISTS idx_tdr_documents_source_record
  ON tdr_documents(source_record_id);
```

---

## 9. Validación e2e esperada

```bash
# 1. Dry run — verificar candidatos
agenteperry tdr download --sector salud --limit 5 --dry-run
# Esperado: tabla con 5 × max_docs filas, status = "pending"

# 2. Descarga real
agenteperry tdr download --sector salud --limit 5 --max-docs 2
# Esperado: ~10 descargas, audit.json saved

# 3. Verificar DB
SELECT download_status, count(*) FROM tdr_documents GROUP BY 1;
# Esperado: downloaded = ~10, failed = 0 (si SEACE disponible)

# 4. Verificar archivos
ls data/tdrs/salud/
# Esperado: directorios por ocid con PDFs/RARs
```

---

## 10. Orden de implementación

1. **Verificar schema** → migración 0004 si necesaria
2. **Modelos** (`DocCandidate`, `DownloadResult`, `DownloadAudit`)
3. **`score_document`** + **`_sanitize_filename`** + tests
4. **`_download_with_retry`** + tests con mock
5. **`fetch_from_db`** + **`fetch_from_jsonl`**
6. **`filter_and_score`**
7. **`_upsert_tdr_document`**
8. **`TdrDownloader.run`**
9. **CLI `tdr download`**
10. **Audit JSON**
11. **Validación e2e**

---

## 11. Archivos de referencia

| Archivo | Qué reusar |
|---|---|
| `tdr/ingestion.py:calculate_sha256` | Función SHA256 ya implementada |
| `collectors/base.py:BulkDownloadCollector.download` | Patrón de descarga con urllib |
| `sync/loader.py:_make_upsert_sql` | Patrón de upsert Postgres |
| `discovery/tdr_discovery.py` | Keywords de sector, fetch_from_jsonl input |
| `data/tdr_recon/recon_20_processes.csv` | Muestra de 20 procesos para test manual |
| `data/tdrs/salud/*.pdf` | Archivos ya descargados para smoke test |

---

## 12. No hacer

- ❌ No parsear PDFs en `downloader.py` (es responsabilidad de `tdr/parsing.py`)
- ❌ No hacer scraping HTML de SEACE (solo descargar por URL directa)
- ❌ No utilizar `requests` como dependencia nueva (usar `urllib.request`)
- ❌ No tocar `chunking.py`, `embeddings.py`, `flags.py`, `search.py`
- ❌ No agregar `tdr_documents` a `source_records` pipeline
