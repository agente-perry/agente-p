# SCRAPER SPEC TEMPLATE — Fuente: <Nombre>

Plantilla específica para specs de collectors. Copia esto en `spec.md` cuando el spec sea un nuevo scraper.

| Campo | Valor |
|-------|-------|
| **Source ID** | `<id_en_sources_yaml>` |
| **Fuente** | <URL oficial> |
| **Prioridad** | P0 \| P1 \| P2 \| P3 |
| **Owner** | @data-engineer |
| **Frecuencia** | manual \| diaria \| semanal \| mensual |

---

## 1. Qué se va a scrapear

Describir qué información expone la fuente y qué subset extraemos.

---

## 2. Método de scraping

- [ ] Direct download (archivo CSV/JSON/XLSX descargable)
- [ ] HTTP API (REST/JSON)
- [ ] Scraping HTML estático (BeautifulSoup)
- [ ] Scraping SPA (Playwright)
- [ ] Form POST (ASP.NET / PHP)
- [ ] PDF parsing (pdfplumber)
- [ ] Otro: ___

### Por qué este método

Justificar. ¿Probaste alternativas?

---

## 3. Auth / Antibot

- Auth requerido: sí / no
- Tipo: OAuth2 / API key / URL params / sesión cookie / ninguno
- CAPTCHA: sí / no — tipo: imagen / recaptcha / hCaptcha
- Rate limit declarado: <N req/min>
- User agent: `Contralatam-Agent/0.1 (+https://contralatam.app/bot)`

---

## 4. Endpoints

| Acción | URL | Método | Params |
|--------|-----|--------|--------|
| List | `https://...` | GET | `?page=N&size=M` |
| Detail | `https://.../{id}` | GET | — |
| Download | `https://.../export` | GET | `?format=csv&year={year}` |

---

## 5. Campos extraídos

| Campo source | Tipo | Campo destino DB | Notas |
|--------------|------|------------------|-------|
| `numero_documento` | string | `canonical_id` | RUC (11 dig) |
| `nombre` | string | `display_name` | trim + uppercase |
| `fecha` | ISO | `metadata.fecha` | JSONB |

---

## 6. Mapeo al grafo

### Entities creadas

```sql
INSERT INTO entities (entity_type, canonical_id, display_name, metadata, sources)
VALUES ('company', $ruc, $razon_social, {...}, ARRAY['SUNAT'])
ON CONFLICT (entity_type, canonical_id)
DO UPDATE SET
  metadata = entities.metadata || EXCLUDED.metadata,
  sources = ARRAY(SELECT DISTINCT unnest(entities.sources || EXCLUDED.sources));
```

### Relationships creadas

| rel_type | source → target | Properties |
|----------|----------------|------------|
| `GANO_CONTRATO` | company → contract | monto, fecha |

---

## 7. Red flags asociados

Indicadores FUNES que esta fuente activa.

- `<flag_id>` — condición — peso

---

## 8. Performance esperado

- Volumen: X registros
- Tamaño de descarga: Y MB
- Tiempo total: Z minutos
- Picos de RAM: M MB (asegurar streaming si > 500MB)

---

## 9. Idempotencia y reproducibilidad

- Conflict key: `(entity_type, canonical_id)` o `(ocid)` o ...
- SHA256 del archivo cacheado para skip de re-parsing
- Resume after failure: ✅ / ❌ — cómo

---

## 10. Tests

- [ ] Fixture VCR.py de respuesta mínima
- [ ] Test parsing → 10 registros válidos
- [ ] Test edge cases: encoding extraño, fila vacía, fecha mal formada
- [ ] Test idempotencia: correr 2x produce el mismo state

---

## 11. Política legal

- ¿Robots.txt permite scraping? Quote relevant section
- ¿Términos de uso? Link
- ¿Hay copyright en el contenido? Sí → solo metadata
- ¿Datos personales? Identificar campos sensibles y decidir si se persisten
