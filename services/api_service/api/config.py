import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = os.path.join(BASE_DIR, "data")

# Video directories - default is a single directory, but can be overridden with VIDEO_DIRS env var
DEFAULT_VIDEO_DIR = os.path.join(DATA_DIR, "videos")
VIDEO_DIRS_ENV = os.environ.get("VIDEO_DIRS", "")
VIDEO_DIRS = [dir.strip() for dir in VIDEO_DIRS_ENV.split(",")] if VIDEO_DIRS_ENV else [DEFAULT_VIDEO_DIR]

# For backward compatibility
VIDEO_DIR = DEFAULT_VIDEO_DIR

# Database
DB_PATH = os.path.join(DATA_DIR, "db", "video_transcriber.db")
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")

# LLM settings
LLM_HOST = os.environ.get("LLM_HOST", "http://localhost:11434/api/generate")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-r1")
