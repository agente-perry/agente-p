# PLAN — SPEC-NNNN

Cómo se implementa el spec. Decisiones técnicas, diagramas, pseudo-código.

---

## Arquitectura

```
[diagrama ASCII o markdown]
```

---

## Componentes a tocar

| Path | Cambio | Owner |
|------|--------|-------|
| `apps/scrapers/collectors/foo/foo_collector.py` | nuevo archivo | @data |
| `packages/db/migrations/NNNN_foo.sql` | nueva migración | @backend |
| `apps/web/app/(public)/foo/page.tsx` | nuevo componente | @frontend |

---

## Modelo de datos

### Tablas nuevas / modificadas

```sql
CREATE TABLE foo (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ...
);
```

### Índices

```sql
CREATE INDEX idx_foo_bar ON foo(bar);
```

---

## API / Interface

### Endpoints

| Método | Path | Body | Response |
|--------|------|------|----------|
| GET | `/api/foo/:id` | — | `{id, bar}` |
| POST | `/api/foo` | `{bar}` | `{id}` |

### CLI

```bash
contralatam foo --option value
```

---

## Flujo de ejecución

1. Paso 1
2. Paso 2
3. Paso 3

---

## Decisiones técnicas

### ¿Por qué X y no Y?

Razonamiento. Tradeoffs. Referencias.

---

## Performance

- Latencia esperada
- Throughput
- Recursos consumidos
- Plan de fallback si supera límites

---

## Seguridad

- Inputs validados con zod / pydantic
- RLS aplicada
- Secretos no hardcoded
- Rate limit respetado

---

## Tests

Estrategia de testing.

- Unit: qué módulos
- Integration: qué flujos
- Fixtures: dónde viven (VCR.py para scrapers)
- Coverage target: ej. 80% para scoring

---

## Rollout

¿Cómo se libera esto?

- [ ] Feature flag (si aplica)
- [ ] Migración backwards-compatible
- [ ] Plan de rollback si algo sale mal
