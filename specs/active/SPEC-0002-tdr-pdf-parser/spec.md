# SPEC-0002: TDR PDF Parser

## Objetivo

Extraer texto limpio por pagina desde PDFs TDR y persistirlo en `tdr_pages`.

## Criterios de aceptacion

- [ ] Parser usa PyMuPDF.
- [ ] Cada pagina preserva `page_number`.
- [ ] Paginas vacias no rompen el pipeline.
- [ ] `parse_status` se actualiza en `tdr_documents`.

## Fuera de alcance

- OCR.
- Embeddings.
- Flags.
