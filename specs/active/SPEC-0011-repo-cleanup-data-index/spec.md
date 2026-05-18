# SPEC-0011: Repo Cleanup, Data Centralization, and Data Index

| Campo | Valor |
|-------|-------|
| **ID** | SPEC-0011 |
| **Estado** | in_progress |
| **Owner** | @miguel |
| **Creado** | 2026-05-17 |
| **Depende de** | SPEC-0000, SPEC-0006 |
| **Bloquea** | Graph team data discovery |

---

## 1. Problema

El directorio `data/` actual tiene estructura dispersa con datos en múltiples ubicaciones sin un índice claro (`data/raw/`, `data/derived/`, `data/filtered/`, `data/tdrs/`, `data/results/`, `data/manual_tdrs/`, `data/tdr_recon/`, `data/golden_set/`). No existe una leyenda única que explique qué contiene cada archivo, cuál es su schema ni cómo fue generado.

Además, hay 2 specs SPEC-0006 duplicadas (`source-registry-and-traceability` y `source-registry-traceability`) sin consolidar.

---

## 2. Objetivo

- Centralizar toda la data scraped bajo `data/scraped/<source>/`.
- Crear `data/INDEX.md` como leyenda maestra con schema, estadísticas y descripción de cada archivo.
- Consolidar las 2 SPEC-0006 duplicadas en una sola.
- Actualizar referencias de código a las rutas viejas.
- Dejar el repositorio navegable para el equipo de Grafos.

---

## 3. Criterios de aceptación

- [ ] `data/INDEX.md` existe con mapa de todo el directorio, schema de cada archivo, y leyenda.
- [ ] Toda la data scrapeada está bajo `data/scraped/<source>/`.
- [ ] Las 2 carpetas SPEC-0006 están consolidadas (1 sobrevive, 1 se archiva).
- [ ] Código Python que referencía rutas viejas actualizado.
- [ ] `data/README.md` actualizado para reflejar la nueva estructura.
- [ ] Tests, ruff, pyright pasan.

---

## 4. Estructura nueva

```
data/
├── scraped/
│   ├── ocds/
│   ├── filtered/
│   ├── tdrs/
│   ├── manual_tdrs/
│   ├── tdr_recon/
│   └── collectors/       ← futuro
├── golden_set/
│   ├── pdfs/
│   └── outputs/
├── results/
├── INDEX.md               ← NUEVO
└── README.md
```

---

## 5. Consolidación SPEC-0006

- Se mantiene: `SPEC-0006-source-registry-traceability` (completada, tasks marcadas como done)
- Se archiva: `SPEC-0006-source-registry-and-traceability` (fue el spec de planificación inicial)

---

## 6. Fuera de alcance

- Cambios en la DB o migraciones.
- Refactor de código no relacionado a paths de data.

---

## 7. Riesgos

- Si algún archivo no se mueve correctamente, el pipeline TDR puede fallar. Mitigación: actualizar referencias de código y testear.
