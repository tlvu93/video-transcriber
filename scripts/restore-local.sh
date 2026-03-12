#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup-dir>" >&2
  exit 1
fi

backup_dir="$1"
if [[ ! -d "$backup_dir" ]]; then
  echo "Backup directory not found: $backup_dir" >&2
  exit 1
fi

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

DATABASE_URL="${DATABASE_URL:-}"
if [[ -z "$DATABASE_URL" ]]; then
  echo "DATABASE_URL must be set before running restore-local.sh" >&2
  exit 1
fi

if ! command -v pg_restore >/dev/null 2>&1; then
  echo "pg_restore is required to restore a PostgreSQL backup." >&2
  exit 1
fi

database_dump="$backup_dir/database.dump"
if [[ ! -f "$database_dump" ]]; then
  echo "Database dump not found: $database_dump" >&2
  exit 1
fi

echo "Restoring PostgreSQL dump from $database_dump"
pg_restore --clean --if-exists --no-owner --dbname="$DATABASE_URL" "$database_dump"

metadata_archive="$backup_dir/app-metadata.tar.gz"
if [[ -f "$metadata_archive" ]]; then
  echo "Restoring app metadata from $metadata_archive"
  tar -xzf "$metadata_archive" -C "$ROOT_DIR"
fi

echo "Restore complete."
