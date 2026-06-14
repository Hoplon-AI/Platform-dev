#!/usr/bin/env bash
set -euo pipefail

echo "Restoring spatial seed dump..."
pg_restore --no-owner --role="$POSTGRES_USER" -d "$POSTGRES_DB" /docker-entrypoint-initdb.d/20_spatial_seed.dump
echo "Restore complete."
