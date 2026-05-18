# Legacy — Visión Anterior y Rama de Respaldo

## Qué es la rama legacy

La rama `legacy/contralatam-platform` conserva la visión original del proyecto: **Contralatam Agent**, un sistema de inteligencia anticorrupción con ConflictMap, Knowledge Graph (Graphiti/Neo4j), Civic Amplifier, scrapers múltiples (OCDS, SUNAT, SEACE, Contraloría) y alertas ciudadanas.

Esa visión es valiosa pero **sobredimensionada para el MVP hackathon**. El foco actual es `AgentePerry TDR Scanner`.

## Cómo acceder al legacy

```bash
# Ver la visión anterior completa
git fetch origin
git checkout legacy/contralatam-platform

# Volver al MVP
git checkout main
```

## Qué vive en legacy/contralatam-platform

| Componente | Descripción |
|------------|-------------|
| `hackl@latam/` | Investigación previa, configs, esquemas, fuentes |
| ConflictMap | Mapa nacional de conflictos de interés |
| Graphiti / Neo4j | Knowledge graph de entidades y relaciones |
| Civic Amplifier | Difusión ciudadana, SMS, WhatsApp |
| Scrapers OCDS | Open Contracting Data Standard Perú |
| Scrapers SUNAT | Padrón reducido, consulta RUC |
| Scrapers Contraloría | Sanciones y alertas |
| Graph schema | `graph_schema.json`, `detection_patterns.yaml` |
| `Fuentes-Hack@Latam` | Catálogo completo de 25+ fuentes |

## Qué NO traer de vuelta sin spec activo

- Ningún scraper de OCDS, SUNAT, Contraloría, CGR, MEF.
- Ningún módulo de Neo4j, Graphiti, ConflictMap.
- Ninguna funcionalidad de Civic Amplifier (SMS, WhatsApp, posts automáticos).
- Ningún mapa nacional o visualización geoespacial.

## Cuándo sí revisitar legacy

- **Post-MVP:** Cuando `AgentePerry TDR Scanner` tenga un dossier funcional con 5-20 TDRs reales.
- **Con spec activo:** Si el equipo decide que una fuente o componente legacy aporta valor, se crea un spec nuevo en `specs/active/` y se implementa desde cero (no se mergea legacy a main).
- **Referencia histórica:** Para entender decisiones de arquitectura, patterns de scraping o estructuras de datos ya exploradas.

## Principio de aislamiento

`main` debe poder entenderse en menos de 2 minutos por un agente de código nuevo. Si un archivo en `main` requiere conocer legacy para ser útil, está en el lugar equivocado.
