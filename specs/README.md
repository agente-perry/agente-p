# specs/ — Spec-Driven Development

Toda funcionalidad nueva pasa por aquí antes de escribir código.

```
specs/
├── _template/          Plantillas base — copiar al crear nuevo spec
│   ├── spec.md         QUÉ y POR QUÉ
│   ├── plan.md         CÓMO (alto nivel)
│   └── tasks.md        TASKS atómicas con checkboxes
├── active/             Specs del MVP AgentePerry TDR Scanner
├── completed/          Specs implementados y mergeados a main
├── deferred/           Specs post-MVP fuera del foco actual
└── archived/           Specs descartados, supersedidos o constitution history
```

---

## Ciclo de vida de un spec

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. PROPONER                                                     │
│    └→ Abrir issue "SPEC: <título>" con template                 │
│                                                                  │
│ 2. ESCRIBIR                                                     │
│    └→ Branch spec/SPEC-NNNN-slug                                │
│    └→ Copiar _template/ a active/SPEC-NNNN-slug/                │
│    └→ Llenar spec.md → plan.md → tasks.md                       │
│    └→ PR a main                                                 │
│                                                                  │
│ 3. REVISAR                                                      │
│    └→ Al menos 1 CODEOWNER aprueba el spec                      │
│    └→ Merge: spec entra a main                                  │
│                                                                  │
│ 4. IMPLEMENTAR                                                  │
│    └→ Branch feat/SPEC-NNNN-slug                                │
│    └→ Cada commit referencia (SPEC-NNNN)                        │
│    └→ Tasks.md tickeado conforme avanza                         │
│    └→ PR de implementación                                      │
│                                                                  │
│ 5. CERRAR                                                       │
│    └→ Reviewer aprueba implementación                           │
│    └→ Merge → mover spec de active/ a completed/                │
│    └→ Tags: SPEC-NNNN-done                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Numeración

- Formato: `SPEC-NNNN` (4 dígitos, secuencial).
- Reservar siguiente número en `specs/_next.txt` (incrementar y commit en mismo PR).
- Nunca reusar un número, ni siquiera para specs archivados.

---

## Estados

| Carpeta | Significado |
|---------|-------------|
| `active/` | En propuesta, revisión o implementación |
| `completed/` | Mergeado en main + funcionando en producción |
| `deferred/` | Fuera del MVP actual; no implementar sin reactivar |
| `archived/` | Descartado, superseded por otro spec, o historial constitucional |

---

## Foco actual

El MVP fue reenfocado a **AgentePerry TDR Scanner**.

Los specs activos deben seguir este orden:

1. `SPEC-0000-focus-tdr-mvp`
2. `SPEC-0001-tdr-manual-loader`
3. `SPEC-0002-tdr-pdf-parser`
4. `SPEC-0003-tdr-chunk-embeddings`
5. `SPEC-0004-tdr-rule-based-flags`
6. `SPEC-0005-tdr-dossier-api`

Los specs de OCDS/SUNAT/ConflictMap/Civic Amplifier quedan en `specs/deferred/` hasta post-MVP.

---

## Buenas prácticas

- **1 spec = 1 outcome**. Si un spec genera 50 tasks → dividir en sub-specs.
- **spec.md sin código.** Solo qué, por qué, criterios de aceptación.
- **plan.md con código mínimo.** Diagramas, pseudocódigo, decisiones clave.
- **tasks.md atómico.** Cada task asignable a una persona en una sesión.
- **Linkea**: spec ↔ issue ↔ branch ↔ PR ↔ commits.

---

## Comandos útiles

```bash
# Siguiente número disponible
cat specs/_next.txt

# Crear nuevo spec
NEXT=$(cat specs/_next.txt)
SLUG="mi-feature"
cp -r specs/_template "specs/active/SPEC-${NEXT}-${SLUG}"
echo $((NEXT + 1)) > specs/_next.txt

# Listar specs activos
ls specs/active/

# Buscar specs por keyword
grep -l "keyword" specs/active/*/spec.md
```
