# Radiografia del Gasto Publico — Pipeline de Video con IA

> **Agente P · Operaciones Glitch** — El knowledge graph anti-corrupcion de Peru genera automaticamente un Reel de Instagram cada dia: toma el caso mas grave detectado por el grafo, lo convierte en guion periodistico con IA, lo narra con voz sintetica y lo publica como video.

📸 Instagram: [@agenteperrylatam](https://www.instagram.com/agenteperrylatam/)

---

## Como funciona

**Agente P** es un knowledge graph (Neo4j AuraDB) que ingiere y cruza datos publicos peruanos: 72,399 contratos OCDS, padron SUNAT, dossiers de riesgo y procedimientos SEACE. Detecta automaticamente 19 tipos de red flags y asigna un `risk_score_v2` a cada contrato.

**Este pipeline** toma ese grafo y lo convierte en contenido:

```
╔══════════════════════════════════╗
║   AGENTE P — Knowledge Graph     ║
║                                  ║
║  72k contratos · 19 red flags    ║
║  risk_score_v2 · Neo4j AuraDB   ║
╚══════════════════════════════════╝
                  │
                  │  Cypher: top caso del dia
                  ▼
         ┌─────────────────┐
         │  CaseSelector   │  ← evita repetir entidades (7 dias)
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │  Claude AI      │  ← genera guion periodistico en español
         │  (voiceover)    │     max 50 palabras, tono directo
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │  ElevenLabs TTS │  ← voz sintetica + word timestamps
         │  voiceover.mp3  │     para karaoke palabra a palabra
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │ Claude Code     │  ← /radiografia: selecciona plantilla
         │ /radiografia    │     Jinja2, llena vars, lint
         │ index.html      │
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │  HyperFrames    │  ← renderiza HTML → MP4
         │  1080×1920 30fps│     animaciones GSAP + karaoke
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────────────────────┐
         │  Instagram Graph API v22        │
         │  @agenteperrylatam              │
         │  instagram.com/agenteperrylatam │
         └─────────────────────────────────┘
```

---

## Que aporta la IA

| Paso | Modelo | Tarea |
|------|--------|-------|
| Guion | Claude (via OpenRouter) | Redacta el voiceover periodistico a partir de los datos del grafo: entidad, monto, patron, fuente |
| Template | Claude Code `/radiografia` | Selecciona la plantilla segun el patron detectado, llena variables, valida animaciones, corre lint |
| Voz | ElevenLabs `eleven_multilingual_v2` | Genera audio con timestamps por palabra para karaoke sincronizado |

El sistema **no inventa datos**. Claude solo narra lo que Agente P ya detecto en fuentes publicas.

---

## Patrones del grafo que se convierten en video

| Patron Agente P | Descripcion | Plantilla |
|-----------------|-------------|-----------|
| `postor_unico_con_proceso_acelerado` | 1 postor + proceso < mitad del promedio sectorial | `postor_unico.html` |
| `proveedor_recurrente` | Mismo proveedor ganando repetidamente (F9, F14) | `proveedor_recurrente.html` |
| `fraccionamiento_contractual` | Contratos partidos al mismo proveedor (F14) | `fraccionamiento.html` |
| `funcionario_sancionado_activo` | Funcionario inhabilitado firmando contratos (F5) | `funcionario_sancionado.html` |

---

## Estructura

```
generar-reels/
├── insights_app/           # Conector Agente P → insight JSON diario
│   ├── main.py             # Consulta grafo, selecciona caso, genera JSON
│   ├── detector.py         # Traduce red flags del grafo a patron de video
│   ├── selector.py         # Elige caso con mayor score evitando repeticion
│   ├── script_generator.py # Claude AI genera voiceover + estructura JSON
│   └── scrapers/           # Colectores de respaldo (SEACE, OCDS, Contraloria)
├── templates/              # HTML Jinja2 por patron (4 plantillas)
├── renderer/assets/
│   ├── animations.css      # 3 capas: ambiente, loops de elemento, GSAP
│   └── animations.js       # initBinaryRain, karaoke, countUp, stampDrop
├── scripts/
│   ├── generate_audio.py   # ElevenLabs TTS + word-level timestamps
│   ├── validate_video.sh   # Validador 7 REGLAs pre/post render
│   ├── publish_ig.sh       # Publica Reel en @agenteperrylatam
│   └── ...
├── skill/SKILL.md          # Definicion del slash command /radiografia
├── examples/
│   └── insight_example_mtc.json
├── run_local.sh            # Pipeline local completo
├── package.json            # HyperFrames ^0.6.15
└── requirements.txt
```

---

## Correr localmente

### Requisitos

- Python 3.12+, Node.js 22+, ffmpeg
- Claude Code CLI: `npm install -g @anthropic-ai/claude-code`
- Acceso a Neo4j AuraDB de Agente P
- Cuentas: ElevenLabs, OpenRouter, Instagram Business

### Setup

```bash
cd generar-reels
cp .env.example .env    # completar con tus keys
pip install -r requirements.txt
npm install
```

### Variables de entorno (`.env`)

```env
# Agente P — Knowledge Graph
NEO4J_URI=neo4j+s://...aura.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=...

# IA — generacion de guion y template
OPENROUTER_API_KEY=sk-or-...
ANTHROPIC_BASE_URL=https://openrouter.ai/api

# Voz
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=pNInz6obpgDQGcFmaJgB

# Publicacion
IG_ACCESS_TOKEN=...
IG_USER_ID=...

# Notificaciones (opcional)
DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
```

### Modos de ejecucion

```bash
# Pipeline completo: grafo → IA → video → Instagram
bash run_local.sh

# Sin publicar en Instagram (para revisar el video antes)
bash run_local.sh --skip-publish

# Sin ElevenLabs (audio silencioso, para probar render)
bash run_local.sh --skip-audio --skip-publish

# Caso de ejemplo MTC sin consultar el grafo ni gastar creditos
bash run_local.sh --use-example --skip-audio --skip-publish
```

---

## Automatizacion GitHub Actions

El workflow `.github/workflows/daily-video.yml` corre sin intervencion humana:

- **Cron**: diario `0 8 * * *` UTC → 3 AM Lima
- **Trigger manual**: `Actions → Run workflow`

### Secrets requeridos en GitHub

| Secret | Descripcion |
|--------|-------------|
| `OPENROUTER_API_KEY` | Claude Code + Claude AI voiceover |
| `ELEVENLABS_API_KEY` | Sintesis de voz |
| `ELEVENLABS_VOICE_ID` | ID de voz |
| `IG_ACCESS_TOKEN` | Meta Graph API — publica en @agenteperrylatam |
| `IG_USER_ID` | ID cuenta Instagram Business |
| `DISCORD_WEBHOOK` | Opcional — notificacion de resultado |

### Primer test recomendado (sin costos)

```
Actions → Run workflow
  usar_ejemplo = true   ← usa caso MTC precargado
  skip_audio   = true   ← audio silencioso, sin ElevenLabs
  modo_test    = true   ← no publica en Instagram
```

---

## Output

| Parametro | Valor |
|-----------|-------|
| Resolucion | 1080 × 1920 px (vertical) |
| Framerate | 30 fps |
| Duracion | 19.5 – 20.5 s |
| Voz | Español peruano, ElevenLabs multilingual v2 |
| Karaoke | Palabra a palabra sincronizada con audio |
| Canal | [@agenteperrylatam](https://www.instagram.com/agenteperrylatam/) |
| Artefactos | Insight JSON (90 dias) + MP4 (30 dias) en GitHub Actions |

---

## Aviso legal

Los datos son de fuentes publicas. El sistema detecta patrones estadisticos, no imputa responsabilidad penal ni judicial. Cada video incluye el disclaimer:

> _"No es sentencia, son datos publicos."_

Fuentes: SEACE · OCDS Peru · Contraloria General · SUNAT
