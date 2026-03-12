import os
import socket
import uuid

from backend.app.runtime.bootstrap import get_app_data_dir, get_repo_root


def get_boolean_env(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


# Base directories
BASE_DIR = get_repo_root()
DATA_DIR = str(get_app_data_dir())

# Video directories - default is a single directory, but can be overridden with VIDEO_DIRS env var
DEFAULT_VIDEO_DIR = os.path.join(DATA_DIR, "videos")
VIDEO_DIRS_ENV = os.environ.get("VIDEO_DIRS", "")
VIDEO_DIRS = [dir.strip() for dir in VIDEO_DIRS_ENV.split(",")] if VIDEO_DIRS_ENV else [DEFAULT_VIDEO_DIR]

# For backward compatibility
VIDEO_DIR = DEFAULT_VIDEO_DIR

# HuggingFace configuration
HF_TOKEN = os.environ.get("HF_TOKEN", None)
JOB_HEARTBEAT_INTERVAL_SECONDS = int(os.environ.get("JOB_HEARTBEAT_INTERVAL_SECONDS", "60"))
JOB_CLAIM_POLL_SECONDS = int(os.environ.get("JOB_CLAIM_POLL_SECONDS", "15"))
WHISPERX_MODEL_NAME = os.environ.get("WHISPERX_MODEL_NAME", "").strip() or None
WHISPERX_COMPUTE_TYPE = os.environ.get("WHISPERX_COMPUTE_TYPE", "").strip() or None
WHISPERX_ENABLE_ALIGNMENT = get_boolean_env("WHISPERX_ENABLE_ALIGNMENT", "1")
WHISPERX_ENABLE_DIARIZATION = get_boolean_env("WHISPERX_ENABLE_DIARIZATION", "1")
WORKER_ID = os.environ.get(
    "WORKER_ID",
    f"transcription-{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}",
)
