# Scraping Techniques — AgentePerry

Guia de tecnicas de scraping para las fuentes de datos de AgentePerry TDR Scanner.

## OECE/SEACE — Portal Datos Abiertos (Angular SPA + Pentaho)

**URL:** `https://contratacionesabiertas.oece.gob.pe/descargas`

### Problema
El portal es una Angular SPA. Los links de descarga son Dinamicos (router Angular). El HTML inicial no contiene los endpoints de datos.

### Paso 1 — Abrir DevTools
1. Abre Chrome en `https://contratacionesabiertas.oece.gob.pe/descargas`
2. Abre DevTools (F12 o click derecho → Inspect)
3. Ve a la pestana **Network**
4. Filtra por **XHR** o **Fetch**

### Paso 2 — Interceptar el endpoint
1. Navega por las categorias del portal (ej: "Procedimientos", "Contratos", "Proveedores")
2. Observa las requests XHR que aparecen
3. Busca requests a URLs como:
   - `bi.seace.gob.pe/pentaho/api/repos/...`
   - `contratacionesabiertas.oece.gob.pe/api/...`
   - URLs contendo `download`, `csv`, `xlsx`, `json`

### Paso 3 — Capturar el endpoint
1. Click derecho sobre la request XHR → **Copy → Copy link address**
2. Verifica que la URL funciona con `curl -L -I <url>`
3. El endpoint tipico de Pentaho es:
   ```
   https://bi.seace.gob.pe/pentaho/api/repos/:public:portal:datosabiertos.html/content?userid=public&password=key
   ```
   con parametros adicionales como `category`, `year`, `format`

### Paso 4 — Usar con el collector
```bash
agenteperry sources collect seace_oece \
  --download-url "https://bi.seace.gob.pe/pentaho/api/repos/..." \
  --download-dir data/raw/oece \
  --out data/derived/oece/procedimientos_2026.jsonl \
  --category procedimientos \
  --year 2026 \
  --format csv
```

### Alternativa — Playwright interception
Si el endpoint cambia frecuentemente, usa Playwright para interceptar la request:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()

    def handle_request(request):
        if "pentaho" in request.url or "download" in request.url:
            print(f"CAPTURED: {request.url}")
            # Guardar la URL para uso posterior
            with open("oece_endpoint.txt", "w") as f:
                f.write(request.url)

    page.on("request", handle_request)
    page.goto("https://contratacionesabiertas.oece.gob.pe/descargas")
    page.wait_for_timeout(5000)
    browser.close()
```

---

## SUNAT — Padron Reducido del RUC

**URL:** `https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html`

### Tecnica
1. La descarga es un ZIP con archivo TXT pipe-delimitado (`|`).
2. Encodings: ISO-8859-1 (Latin-1), NO UTF-8.
3. Estructura del TXT: cada linea es un RUC con campos separados por `|`.

### Pasos
```bash
# Descargar el ZIP
curl -L -o data/raw/sunat/padron_reducido.zip \
  "https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html"

# Descomprimir
unzip -o data/raw/sunat/padron_reducido.zip -d data/raw/sunat/

# Verificar encoding
file data/raw/sunat/mrc137_padron_reducido.txt

# Convertir a UTF-8 si es necesario
iconv -f ISO-8859-1 -t UTF-8 data/raw/sunat/mrc137_padron_reducido.txt \
  > data/derived/sunat/padron_reducido_utf8.txt
```

### Estructura del TXT (primeros campos)
```
204笔笔笔笔笔|RAZON SOCIAL|CONTRIBUYENTE|direccion|...]
```

---

## Contraloria — Registro de Sanciones

**URL:** `https://www.gob.pe/institucion/contraloria/informes-publicaciones/2706979-registro-de-sanciones-inscritas-y-vigentes`

### Tecnica
USA PLAYWRIGHT. La descarga es un XLSX interceptado via network request.

```python
from playwright.sync_api import sync_playwright

def download_sanciones():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.contexts[0]
        page = context.new_page()

        # Interceptar descarga de XLSX
        with page.expect_download() as dl_info:
            page.goto("https://www.gob.pe/institucion/contraloria/informes-publicaciones/2706979-registro-de-sanciones-inscritas-y-vigentes")
            page.click("text=Descargar Excel")  # Ajustar selector

        download = dl_info.value
        download.save_as("data/raw/contraloria/sanciones.xlsx")
        browser.close()
```

---

## OCDS Peru — Open Contracting Data Standard

**URLs:**
- 2026: `https://data.open-contracting.org/es/publication/135/download?name=2026.jsonl.gz`
- 2025: `https://data.open-contracting.org/es/publication/135/download?name=2025.jsonl.gz`

### Tecnica
Descarga directa con curl. El archivo es `.jsonl.gz` (gzipped JSON Lines).

```bash
# Descargar (77MB para 2026)
curl -L -o data/raw/ocds/2026.jsonl.gz \
  "https://data.open-contracting.org/es/publication/135/download?name=2026.jsonl.gz"

# Verificar contenido sin descomprimir
gunzip -c data/raw/ocds/2026.jsonl.gz | head -1 | python -m json.tool

# Estadisticas
gunzip -c data/raw/ocds/2026.jsonl.gz | wc -l  # Numero de records
```

### Procesamiento
```bash
# Colectar records
agenteperry sources collect ocds_peru \
  --input data/raw/ocds/2026.jsonl.gz \
  --out data/derived/ocds/contracts_2026.jsonl

# Mapear a grafo
agenteperry graph map-records \
  data/derived/ocds/contracts_2026.jsonl \
  --out data/derived/ocds/graph_2026.jsonl

# Subir a Postgres
DATABASE_URL="postgresql://..." \
agenteperry db sync \
  data/derived/ocds/contracts_2026.jsonl \
  --graph data/derived/ocds/graph_2026.jsonl
```

---

## MEF — CKAN Datos Abiertos

**URL:** `https://datosabiertos.mef.gob.pe/dataset`

### Problema
El collector CKAN encontro que la API devuelve HTML en lugar de JSON.

### Diagnostico
```python
import requests
resp = requests.get("https://datosabiertos.mef.gob.pe/api/3/action/package_list")
print(resp.headers.get("content-type"))  # text/html; charset=UTF-8
```

### Solucion
Verificar si la API de CKAN esta en un path diferente o si requiere autenticacion.

---

## Ley 32069 — Ley General de Contrataciones (PDF legal)

**URL:** `https://www.gob.pe/institucion/oece/colecciones/45029-ley-n-32069-ley-general-de-contrataciones-publicas-y-su-reglamento`

### Tecnica
Descarga el PDF y usa el pipeline TDR:

```bash
# Descargar PDF
curl -L -o data/raw/ley_32069/ley_32069.pdf \
  "https://busv1.oece.gob.pe/normas/archivos/Ley_32069.pdf"

# Cargar al pipeline TDR
agenteperry tdr load-pipeline \
  data/raw/ley_32069/ley_32069.pdf \
  --source ley_32069 \
  --out data/derived/ley_32069/chunks.jsonl
```
