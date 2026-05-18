#!/usr/bin/env bash
# DROP database and recreate from migrations. DEV ONLY.

set -euo pipefail

if [ "${ALLOW_RESET:-}" != "yes" ]; then
  echo "⚠️  This will DROP all data in contralatam DB."
  read -rp "Type 'yes' to confirm: " confirm
  [ "$confirm" = "yes" ] || { echo "Aborted."; exit 1; }
fi

DB_HOST="${PGHOST:-localhost}"
DB_PORT="${PGPORT:-5432}"
DB_USER="${PGUSER:-contralatam}"
DB_NAME="${PGDATABASE:-contralatam}"

PGPASSWORD="${POSTGRES_PASSWORD:-dev_password}" psql \
  -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres <<EOF
DROP DATABASE IF EXISTS $DB_NAME;
CREATE DATABASE $DB_NAME;
EOF

echo "✅ Database recreated"

bash "$(dirname "$0")/db-migrate.sh"
