#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

wait_for_container_state() {
    local service="$1"
    local desired_state="$2"
    local attempts="${3:-30}"
    local sleep_seconds="${4:-2}"

    for ((attempt = 1; attempt <= attempts; attempt++)); do
        local container_id
        container_id="$(docker compose ps -q "$service")"
        if [ -n "$container_id" ]; then
            local current_state
            if [ "$desired_state" = "healthy" ]; then
                current_state="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id" 2>/dev/null || true)"
            else
                current_state="$(docker inspect -f '{{.State.Status}}' "$container_id" 2>/dev/null || true)"
            fi

            if [ "$current_state" = "$desired_state" ]; then
                echo "$service is $desired_state."
                return 0
            fi
        fi

        sleep "$sleep_seconds"
    done

    echo "Timed out waiting for $service to become $desired_state."
    docker compose ps "$service" || true
    docker compose logs --no-color --tail=80 "$service" || true
    return 1
}

wait_for_url() {
    local label="$1"
    local url="$2"
    local attempts="${3:-30}"
    local sleep_seconds="${4:-2}"

    for ((attempt = 1; attempt <= attempts; attempt++)); do
        if curl --fail --silent --show-error "$url" >/dev/null; then
            echo "$label is responding."
            return 0
        fi

        sleep "$sleep_seconds"
    done

    echo "Timed out waiting for $label at $url."
    return 1
}

resolve_published_port() {
    local service="$1"
    local container_port="$2"
    local host_port

    host_port="$(docker compose port "$service" "$container_port" | awk -F: 'NR==1 {print $NF}')"

    if [ -z "$host_port" ]; then
        echo "Unable to resolve published port for $service:$container_port." >&2
        return 1
    fi

    printf '%s\n' "$host_port"
}

if [ -f ".env" ]; then
    echo "Refreshing generated volume mounts..."
    ./scripts/setup-volumes.sh
fi

echo "Building and starting the stack..."
docker compose up -d --build

echo "Waiting for container health checks..."
wait_for_container_state postgres healthy 20 2
wait_for_container_state ollama healthy 45 2
wait_for_container_state api healthy 30 2
wait_for_container_state frontend healthy 20 2
wait_for_container_state transcription-worker running 20 2
wait_for_container_state summarization-worker running 20 2
wait_for_container_state translation-worker running 20 2
wait_for_container_state watcher running 20 2

API_PORT="$(resolve_published_port api 8000)"
FRONTEND_PORT="$(resolve_published_port frontend 80)"

API_URL="${API_URL:-http://127.0.0.1:${API_PORT}}"
FRONTEND_URL="${FRONTEND_URL:-http://127.0.0.1:${FRONTEND_PORT}}"

echo "Checking API health..."
wait_for_url "API health" "${API_URL%/}/healthz" 20 2

echo "Checking frontend health..."
wait_for_url "Frontend root" "${FRONTEND_URL%/}/" 20 2
wait_for_url "Frontend API proxy" "${FRONTEND_URL%/}/api/healthz" 20 2

echo "Checking worker imports..."
docker compose exec -T api python -c "import backend.app.entrypoints.api"
docker compose exec -T transcription-worker python -c "import backend.app.entrypoints.transcription_worker"
docker compose exec -T summarization-worker python -c "import backend.app.entrypoints.summarization_worker"
docker compose exec -T translation-worker python -c "import backend.app.entrypoints.translation_worker"
docker compose exec -T watcher python -c "import backend.app.entrypoints.watcher"

echo "Smoke checks passed."
