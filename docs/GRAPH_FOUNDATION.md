# Graph Foundation in Postgres

## Por qué Postgres y no Neo4j

Para el hackathon necesitamos velocidad de desarrollo, no infraestructura extra. Postgres con pgvector + relaciones ya soporta:

- Búsqueda semántica (embeddings).
- Traversals recursivos (CTEs).
- JSONB flexible para metadata.
- Índices GIN para arrays y JSON.
- Full-text search en español.

Neo4j/Graphiti quedan para post-MVP si el volumen lo justifica.

## Modelo De Grafo

```text
source_entities       (nodos)
  -> source_relationships  (aristas)
```

### Tipos de entidad (nodos)

| Tipo | Descripción | Ejemplo |
|------|-------------|---------|
| `company` | Empresa proveedora | RUC 20131312955 |
| `public_entity` | Entidad del Estado | Ministerio de Salud |
| `person` | Persona natural | Funcionario, candidato |
| `political_org` | Organización política | Partido X |
| `sancion` | Sanción administrativa | Resolución N° 123 |
| `audit_report` | Informe de control | CGR-2024-456 |
| `electoral_contribution` | Aporte electoral | S/ 50,000 a Partido X |
| `interest_declaration` | DJI | Declaración jurada |
| `legal_norm` | Norma legal | Ley 32069 |

### Tipos de relación (aristas)

| Relación | Origen | Destino | Significado |
|----------|--------|---------|-------------|
| `GANO_CONTRATO` | company | contract | Empresa ganó contrato |
| `COMPRO_A` | public_entity | company | Entidad compró a empresa |
| `POSTULO_EN` | company | contract | Empresa postuló |
| `MIEMBRO_COMITE` | person | contract | Funcionario en comité |
| `FUNCIONARIO_EN` | person | public_entity | Persona trabaja en entidad |
| `REPRESENTANTE_DE` | person | company | Persona representa empresa |
| `FAMILIAR_DE` | person | person | Parentesco |
| `APORTO_A` | company | political_org | Empresa aportó a partido |
| `CANDIDATO_EN` | person | political_org | Persona candidata |
| `GOVERNS` | political_org | public_entity | Partido gobierna entidad |
| `MISMO_DOMICILIO` | company | company | Misma dirección fiscal |
| `MISMO_REPR_LEGAL` | company | company | Mismo representante |
| `TIENE_SANCION` | person | sancion | Persona sancionada |
| `MENCIONADO_EN` | person | audit_report | Mencionado en informe |
| `VINCULO_DJI` | person | company | Vínculo declarado en DJI |

## Ejemplo De Query: Subgrafo Desde Un RUC

```sql
SELECT * FROM get_subgraph('20131312955', 3);
```

Devuelve todas las entidades conectadas al RUC hasta profundidad 3.

## Ejemplo De Query: Conflictos De Interés

```sql
-- Funcionario en comité de selección cuya empresa familiar ganó contrato
SELECT
  p.display_name AS funcionario,
  fam.display_name AS familiar,
  emp.display_name AS empresa_ganadora,
  c.external_id AS contrato
FROM source_entities p
JOIN source_relationships r_com ON r_com.source_id = p.id AND r_com.rel_type = 'MIEMBRO_COMITE'
JOIN source_records c ON c.id::text = r_com.properties->>'contract_id'
JOIN source_relationships r_fam ON r_fam.source_id = p.id AND r_fam.rel_type = 'FAMILIAR_DE'
JOIN source_entities fam ON fam.id = r_fam.target_id
JOIN source_relationships r_repr ON r_repr.source_id = fam.id AND r_repr.rel_type = 'REPRESENTANTE_DE'
JOIN source_entities emp ON emp.id = r_repr.target_id
WHERE c.supplier_ruc = emp.canonical_id;
```

## Performance

- Índices en `(source_id, rel_type)` y `(target_id, rel_type)`.
- CTE recursivo con `max_depth` limitado.
- Particionar `source_records` por `period_year` si supera 10M registros.
- Materializar vistas frecuentes (ej: empresas con domicilio compartido).

## Límite Conocido

Postgres CTE recursivo no es tan rápido como Neo4j para grafos masivos (>100M aristas). Para el hackathon con datos de 3-5 años es suficiente.
