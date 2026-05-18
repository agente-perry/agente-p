# Agent Skills — AgentePerry TDR Scanner

This repo uses project-level skills from the open agent skills ecosystem. They are installed for Claude Code, OpenCode and Codex-compatible agents.

Research source: `https://skills.sh/` leaderboard and package listings.

Use the modern CLI:

```bash
npx skills --help
```

Do not use the older `skillsadd` package for this repo; current `skills.sh` docs and CLI support `npx skills add ...`.

## Installed Skill Stack

### Project-Specific Guardrail

| Skill | Source | When to use |
|-------|--------|-------------|
| `agenteperry-tdr-scanner` | local repo | Always for TDR Scanner work; keeps agents aligned to MVP and blocks deferred ConflictMap/Graphiti work |

### Planning and Execution

| Skill | Source | When to use |
|-------|--------|-------------|
| `writing-plans` | `obra/superpowers` | Before multi-step specs or implementation plans |
| `executing-plans` | `obra/superpowers` | When executing an approved plan |
| `test-driven-development` | `obra/superpowers` | Before implementing new behavior |
| `systematic-debugging` | `obra/superpowers` | When tests, parsing or CLI behavior fails |
| `verification-before-completion` | `obra/superpowers` | Before claiming work is done |
| `requesting-code-review` | `obra/superpowers` | Before PR or merge |
| `using-git-worktrees` | `obra/superpowers` | When parallel work needs isolation |
| `subagent-driven-development` | `obra/superpowers` | When independent tasks can be split across agents |
| `finishing-a-development-branch` | `obra/superpowers` | Before PR/merge cleanup |

### Architecture and Product Thinking

| Skill | Source | When to use |
|-------|--------|-------------|
| `improve-codebase-architecture` | `mattpocock/skills` | Review `agenteperry/tdr` boundaries and testability |
| `diagnose` | `mattpocock/skills` | Deep debugging loop for hard parser/API bugs |
| `tdd` | `mattpocock/skills` | Red-green-refactor feature work |
| `to-prd` | `mattpocock/skills` | Convert discovery into executable product requirements |
| `grill-me` | `mattpocock/skills` | Prepare for hackathon judging and hard design questions |
| `zoom-out` | `mattpocock/skills` | Re-check scope when the repo starts drifting |

### Data, PDFs and Database

| Skill | Source | When to use |
|-------|--------|-------------|
| `pdf` | `anthropics/skills` | Inspecting or manipulating PDF/TDR documents |
| `xlsx` | `anthropics/skills` | Handling spreadsheet manifests or exports |
| `supabase` | `supabase/agent-skills` | Supabase setup, RLS, pgvector, auth or storage |
| `supabase-postgres-best-practices` | `supabase/agent-skills` | Schema/index/query review for `tdr_*` tables |

### Web Research and Future Scraping

| Skill | Source | When to use |
|-------|--------|-------------|
| `firecrawl-search` | `firecrawl/cli` | Web research with full-page extraction |
| `firecrawl-scrape` | `firecrawl/cli` | Reading public pages that WebFetch cannot parse well |
| `firecrawl-map` | `firecrawl/cli` | Discovering source URLs on a public site |
| `firecrawl-parse` | `firecrawl/cli` | Parsing local documents into markdown for analysis |
| `just-scrape` | `scrapegraphai/just-scrape` | Structured extraction from websites when needed |
| `playwright-best-practices` | `currents-dev/playwright-best-practices-skill` | Future browser tests or JS-heavy source exploration |

Important: these do not authorize building ONPE/JNE/SUNARP/ConflictMap now. They are available for research and future `seace_oece_tdr` work only after the active specs allow it.

### Frontend and API Demo

| Skill | Source | When to use |
|-------|--------|-------------|
| `frontend-design` | `anthropics/skills` | Dossier UI design after data core exists |
| `webapp-testing` | `anthropics/skills` | End-to-end testing of future dossier API/UI |
| `next-best-practices` | `vercel-labs/next-skills` | Next.js route handlers and App Router decisions |
| `vercel-react-best-practices` | `vercel-labs/agent-skills` | React performance and component patterns |
| `vercel-composition-patterns` | `vercel-labs/agent-skills` | Component API design |
| `web-design-guidelines` | `vercel-labs/agent-skills` | UX/accessibility review |
| `impeccable` | `pbakaus/impeccable` | Final frontend polish when UI exists |

### Skill and MCP Authoring

| Skill | Source | When to use |
|-------|--------|-------------|
| `skill-creator` | `anthropics/skills` | Create AgentePerry-specific skills |
| `mcp-builder` | `anthropics/skills` | Build MCP tools for Supabase/TDR queries if needed |

## Not Installed On Purpose

The following are intentionally deferred because they conflict with the current MVP focus:

- Graphiti/Neo4j skills.
- ConflictMap-specific detector skills.
- OCDS/SUNAT/ONPE/JNE/SUNARP skills.
- SMS/campaign distribution skills.

If the roadmap changes, move the relevant spec from `specs/deferred/` to `specs/active/` first.

## Reinstall

Run:

```bash
bash scripts/install-agent-skills.sh
```

Verify:

```bash
npx skills list --json
```
