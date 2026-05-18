#!/usr/bin/env bash
# Install repo git hooks for current clone.
# Run once after cloning: bash scripts/install-hooks.sh

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
SRC="$REPO_ROOT/.github/hooks"
DEST="$REPO_ROOT/.git/hooks"

for hook in "$SRC"/*; do
  name="$(basename "$hook")"
  cp "$hook" "$DEST/$name"
  chmod +x "$DEST/$name"
  echo "✓ Installed $name"
done

echo ""
echo "Git hooks installed. Commits without (SPEC-NNNN) will be rejected."
