import os
import socket
import uuid

from backend.app.runtime.bootstrap import get_app_data_dir, get_repo_root


def _get_first_nonempty_env(*names: str, default: str) -> str:
    """Return the first non-empty environment value from the provided names."""
    for name in names:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return default


# Base directories
BASE_DIR = get_repo_root()
DATA_DIR = str(get_app_data_dir())

# Video and transcription directories
VIDEO_DIR = os.path.join(DATA_DIR, "videos")


# LLM settings
LLM_HOST = os.environ.get("LLM_HOST", "http://localhost:11434/api/generate")
DEFAULT_SUMMARIZATION_LLM_MODEL = "mistral-small3.1"
LLM_MODEL = _get_first_nonempty_env(
    "SUMMARIZATION_LLM_MODEL",
    "LLM_MODEL",
    default=DEFAULT_SUMMARIZATION_LLM_MODEL,
)
LLM_REQUEST_TIMEOUT_SECONDS = int(os.environ.get("LLM_REQUEST_TIMEOUT_SECONDS", "900"))
OLLAMA_HEALTHCHECK_TTL_SECONDS = int(
    os.environ.get("OLLAMA_HEALTHCHECK_TTL_SECONDS", "60")
)
SUMMARY_MAX_TOKENS = int(os.environ.get("SUMMARY_MAX_TOKENS", "1024"))
SUMMARIZATION_CONTENT_PROFILE = os.environ.get(
    "SUMMARIZATION_CONTENT_PROFILE",
    "auto",
).strip().lower() or "auto"
JOB_HEARTBEAT_INTERVAL_SECONDS = int(os.environ.get("JOB_HEARTBEAT_INTERVAL_SECONDS", "60"))
JOB_CLAIM_POLL_SECONDS = int(os.environ.get("JOB_CLAIM_POLL_SECONDS", "15"))
WORKER_ID = os.environ.get(
    "WORKER_ID",
    f"summarization-{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}",
)
