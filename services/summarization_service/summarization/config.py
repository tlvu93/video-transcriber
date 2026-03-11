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
DEFAULT_SUMMARIZATION_LLM_MODEL = "mistral-small3.1"
LLM_MODEL = _get_first_nonempty_env(
    "SUMMARIZATION_LLM_MODEL",
    "LLM_MODEL",
    default=DEFAULT_SUMMARIZATION_LLM_MODEL,
)
JOB_HEARTBEAT_INTERVAL_SECONDS = int(os.environ.get("JOB_HEARTBEAT_INTERVAL_SECONDS", "60"))
JOB_CLAIM_POLL_SECONDS = int(os.environ.get("JOB_CLAIM_POLL_SECONDS", "15"))
WORKER_ID = os.environ.get(
    "WORKER_ID",
    f"summarization-{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}",
)
