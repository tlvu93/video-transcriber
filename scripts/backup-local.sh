#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

DATABASE_URL="${DATABASE_URL:-}"
if [[ -z "$DATABASE_URL" ]]; then
  echo "DATABASE_URL must be set before running backup-local.sh" >&2
  exit 1
fi

if ! command -v pg_dump >/dev/null 2>&1; then
  echo "pg_dump is required to create a PostgreSQL backup." >&2
  exit 1
fi

timestamp="$(date -u +"%Y%m%dT%H%M%SZ")"
backup_root="${BACKUP_ROOT:-$ROOT_DIR/backups}"
backup_dir="${1:-$backup_root/$timestamp}"
mkdir -p "$backup_dir"

echo "Writing PostgreSQL backup to $backup_dir/database.dump"
pg_dump --format=custom --file="$backup_dir/database.dump" "$DATABASE_URL"

metadata_paths=()
for candidate in .env.example docker-compose.yml README.md docs/operations data/translations data/object-storage; do
  if [[ -e "$candidate" ]]; then
    metadata_paths+=("$candidate")
  fi
done

if (( ${#metadata_paths[@]} > 0 )); then
  echo "Archiving app metadata to $backup_dir/app-metadata.tar.gz"
  tar -czf "$backup_dir/app-metadata.tar.gz" "${metadata_paths[@]}"
fi

cat > "$backup_dir/manifest.txt" <<EOF
created_at_utc=$timestamp
database_dump=database.dump
metadata_archive=$( [[ -f "$backup_dir/app-metadata.tar.gz" ]] && echo "app-metadata.tar.gz" || echo "" )
note=Video files are not included. This backup contains PostgreSQL data plus app metadata/cache directories only.
EOF

echo "Backup complete: $backup_dir"
