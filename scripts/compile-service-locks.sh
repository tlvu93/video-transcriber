#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TRANSCRIPTION_PYTHON_PLATFORM="${TRANSCRIPTION_PYTHON_PLATFORM:-aarch64-unknown-linux-gnu}"

for extra in api summarization transcription translation watcher; do
    case "$extra" in
    api)
        output_path="services/api_service/requirements.lock"
        ;;
    summarization)
        output_path="services/summarization_service/requirements.lock"
        ;;
    transcription)
        output_path="services/transcription_service/requirements.lock"
        ;;
    translation)
        output_path="services/translation_service/requirements.lock"
        ;;
    watcher)
        output_path="services/watcher_service/requirements.lock"
        ;;
    esac

    echo "Compiling ${output_path} from pyproject extra '${extra}'..."
    if [ "$extra" = "transcription" ]; then
        uv pip compile \
            pyproject.toml \
            --extra "$extra" \
            --python-version 3.13 \
            --python-platform "$TRANSCRIPTION_PYTHON_PLATFORM" \
            -o "$output_path"
    else
        uv pip compile pyproject.toml --extra "$extra" --python-version 3.13 -o "$output_path"
    fi
done
