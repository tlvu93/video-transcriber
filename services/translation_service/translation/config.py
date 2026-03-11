import os
import socket
import uuid
from pathlib import Path


def _get_first_nonempty_env(*names: str, default: str) -> str:
    """Return the first non-empty environment value from the provided names."""
    for name in names:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return default


# Base directories
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = os.path.join(BASE_DIR, "data")

# Video and transcription directories
VIDEO_DIR = os.path.join(DATA_DIR, "videos")

# API service
API_URL = os.environ.get("API_URL", "http://api:8000")

# LLM settings
LLM_HOST = os.environ.get("LLM_HOST", "http://localhost:11434/api/generate")
DEFAULT_TRANSLATION_LLM_MODEL = "qwen3:14b"
LLM_MODEL = _get_first_nonempty_env(
    "TRANSLATION_LLM_MODEL",
    "LLM_MODEL",
    default=DEFAULT_TRANSLATION_LLM_MODEL,
)
LLM_REQUEST_TIMEOUT_SECONDS = int(os.environ.get("LLM_REQUEST_TIMEOUT_SECONDS", "900"))
OLLAMA_HEALTHCHECK_TTL_SECONDS = int(
    os.environ.get("OLLAMA_HEALTHCHECK_TTL_SECONDS", "60")
)
TRANSLATION_BATCH_SIZE = int(os.environ.get("TRANSLATION_BATCH_SIZE", "8"))
TRANSLATION_BATCH_MAX_CHARS = int(
    os.environ.get("TRANSLATION_BATCH_MAX_CHARS", "6000")
)
TRANSLATION_CACHE_DIR = os.environ.get(
    "TRANSLATION_CACHE_DIR",
    os.path.join(DATA_DIR, "translations"),
)
JOB_HEARTBEAT_INTERVAL_SECONDS = int(os.environ.get("JOB_HEARTBEAT_INTERVAL_SECONDS", "60"))
JOB_CLAIM_POLL_SECONDS = int(os.environ.get("JOB_CLAIM_POLL_SECONDS", "15"))
WORKER_ID = os.environ.get(
    "WORKER_ID",
    f"translation-{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}",
)

# Supported languages
SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish", 
    "fr": "French",
    "de": "German",
    "ja": "Japanese",
}
