#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

API_URL="${API_URL:-http://localhost:${API_PORT:-8000}}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:${FRONTEND_PORT:-3000}}"

echo "Building and starting the stack..."
docker compose up -d --build

echo "Waiting for PostgreSQL..."
docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-videotranscriber}"

echo "Checking API health..."
curl --fail --silent --show-error "$API_URL/" >/dev/null

echo "Checking frontend health..."
curl --fail --silent --show-error "$FRONTEND_URL/" >/dev/null

echo "Checking worker imports..."
docker compose exec -T transcription-worker python -c "import transcription.main"
docker compose exec -T summarization-worker python -c "import summarization.main"
docker compose exec -T translation-worker python -c "import translation.main"
docker compose exec -T watcher python -c "import watcher.watcher"

echo "Smoke checks passed."
