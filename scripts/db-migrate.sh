#!/usr/bin/env bash
# Apply all migrations in packages/db/migrations/ in order.
# Honors $DATABASE_URL (defaults to local docker postgres).

set -euo pipefail

DB_URL="${DATABASE_URL:-postgresql://contralatam:dev_password@localhost:5432/contralatam}"
MIGRATIONS_DIR="$(dirname "$0")/../packages/db/migrations"

echo "🗃  Applying migrations to: ${DB_URL%%@*}@***"

for migration in "$MIGRATIONS_DIR"/*.sql; do
  echo "  → $(basename "$migration")"
  psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$migration" > /dev/null
done

echo "✅ All migrations applied"
