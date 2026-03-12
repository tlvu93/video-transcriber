import os

from backend.app.runtime.bootstrap import get_app_data_dir, get_repo_root


def normalize_database_url(raw_database_url: str) -> str:
    """Prefer the psycopg3 SQLAlchemy dialect when no PostgreSQL driver is specified."""
    if raw_database_url.startswith("postgresql://"):
        return raw_database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    return raw_database_url


def to_psycopg_conninfo(database_url: str) -> str:
    """Convert the SQLAlchemy psycopg URL into a plain libpq-compatible DSN."""
    if database_url.startswith("postgresql+psycopg://"):
        return database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    return database_url


def get_boolean_env(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def get_live_updates_channel() -> str:
    channel = os.environ.get("LIVE_UPDATES_CHANNEL", "video_transcriber_live_updates").strip()
    if not channel:
        raise RuntimeError("LIVE_UPDATES_CHANNEL must not be empty.")

    if not all(character.isalnum() or character == "_" for character in channel):
        raise RuntimeError(
            "LIVE_UPDATES_CHANNEL may only contain letters, numbers, and underscores."
        )

    return channel


def get_database_url() -> str:
    """Require a PostgreSQL database URL for all API runtime modes."""
    raw_database_url = os.environ.get("DATABASE_URL")
    if not raw_database_url:
        raise RuntimeError("DATABASE_URL must be set to a PostgreSQL connection string.")

    database_url = normalize_database_url(raw_database_url)
    if not database_url.startswith("postgresql"):
        raise RuntimeError("DATABASE_URL must point to PostgreSQL. SQLite is no longer supported.")

    return database_url

# Base directories
BASE_DIR = get_repo_root()
DATA_DIR = str(get_app_data_dir())

# Video directories - default is a single directory, but can be overridden with VIDEO_DIRS env var
DEFAULT_VIDEO_DIR = os.path.join(DATA_DIR, "videos")
VIDEO_DIRS_ENV = os.environ.get("VIDEO_DIRS", "")
VIDEO_DIRS = [dir.strip() for dir in VIDEO_DIRS_ENV.split(",")] if VIDEO_DIRS_ENV else [DEFAULT_VIDEO_DIR]

# For backward compatibility
VIDEO_DIR = DEFAULT_VIDEO_DIR

# Database
DATABASE_URL = get_database_url()
PSYCOPG_CONNINFO = to_psycopg_conninfo(DATABASE_URL)

# Queue leasing
JOB_LEASE_DURATION_SECONDS = int(os.environ.get("JOB_LEASE_DURATION_SECONDS", "600"))
JOB_HEARTBEAT_INTERVAL_SECONDS = int(os.environ.get("JOB_HEARTBEAT_INTERVAL_SECONDS", "60"))

# Live updates
LIVE_UPDATES_NOTIFY_ENABLED = get_boolean_env("LIVE_UPDATES_NOTIFY_ENABLED", "1")
LIVE_UPDATES_RECONNECT_SECONDS = int(os.environ.get("LIVE_UPDATES_RECONNECT_SECONDS", "5"))
LIVE_UPDATES_CHANNEL = get_live_updates_channel()

# LLM settings
LLM_HOST = os.environ.get("LLM_HOST", "http://localhost:11434/api/generate")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3:14b")
