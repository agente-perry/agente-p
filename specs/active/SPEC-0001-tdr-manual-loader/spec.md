# SPEC-0001: TDR Manual Loader

## Objetivo

Cargar metadata de TDRs desde CSV y registrar documentos en `tdr_documents`.

## Input CSV

```csv
external_id,title,entity_name,procedure_code,source_url,file_url,sector,region,district,publication_date,estimated_value
```

## Criterios de aceptacion

- [ ] Comando `agenteperry tdr load-manual <metadata.csv>` valida columnas requeridas.
- [ ] Upsert idempotente en `tdr_documents`.
- [ ] Tests con fixture pequena.
- [ ] Logs claros.

## Fuera de alcance

- Descargar PDFs.
- Parsear PDFs.
- Embeddings.
- Flags.
