#!/usr/bin/env bash
set -euo pipefail

# Project-level agent skills for Claude Code, OpenCode and Codex-compatible agents.
# Keep this aligned with docs/AGENT_SKILLS.md.

AGENTS=(claude-code opencode codex)

npx skills add anthropics/skills \
  --agent "${AGENTS[@]}" \
  --skill pdf xlsx skill-creator mcp-builder frontend-design webapp-testing \
  -y --copy

npx skills add supabase/agent-skills \
  --agent "${AGENTS[@]}" \
  --skill supabase supabase-postgres-best-practices \
  -y --copy

npx skills add vercel-labs/agent-skills \
  --agent "${AGENTS[@]}" \
  --skill vercel-react-best-practices web-design-guidelines vercel-composition-patterns \
  -y --copy

npx skills add vercel-labs/next-skills \
  --agent "${AGENTS[@]}" \
  --skill next-best-practices \
  -y --copy

npx skills add obra/superpowers \
  --agent "${AGENTS[@]}" \
  --skill writing-plans executing-plans systematic-debugging test-driven-development verification-before-completion requesting-code-review finishing-a-development-branch using-git-worktrees subagent-driven-development \
  -y --copy

npx skills add mattpocock/skills \
  --agent "${AGENTS[@]}" \
  --skill improve-codebase-architecture tdd diagnose to-prd grill-me zoom-out setup-matt-pocock-skills \
  -y --copy

npx skills add pbakaus/impeccable \
  --agent "${AGENTS[@]}" \
  --skill impeccable \
  -y --copy

npx skills add currents-dev/playwright-best-practices-skill \
  --agent "${AGENTS[@]}" \
  --skill playwright-best-practices \
  -y --copy

npx skills add firecrawl/cli \
  --agent "${AGENTS[@]}" \
  --skill firecrawl-search firecrawl-scrape firecrawl-parse firecrawl-map \
  -y --copy

npx skills add scrapegraphai/just-scrape \
  --agent "${AGENTS[@]}" \
  --skill just-scrape \
  -y --copy

npx skills list --json
