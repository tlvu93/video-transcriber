#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

dump_failure_context() {
    local exit_code="$1"
    if [ "$exit_code" -eq 0 ]; then
        return
    fi

    echo "E2E smoke failed. Collecting container status and logs..."
    docker compose ps || true
    for service in api frontend transcription-worker summarization-worker translation-worker watcher; do
        echo "--- ${service} logs ---"
        docker compose logs --no-color --tail=120 "$service" || true
    done
}

on_exit() {
    local exit_code="$?"
    dump_failure_context "$exit_code"
}

trap on_exit EXIT

export WHISPERX_MODEL_NAME="${WHISPERX_MODEL_NAME:-tiny}"
export WHISPERX_ENABLE_DIARIZATION="${WHISPERX_ENABLE_DIARIZATION:-0}"

./scripts/smoke-compose.sh
API_PORT="$(docker compose port api 8000 | awk -F: 'END{print $NF}')"
if [ -z "${API_PORT}" ]; then
    echo "Failed to resolve published API port."
    exit 1
fi
export API_URL="http://127.0.0.1:${API_PORT}"
python3 ./scripts/e2e_smoke.py
