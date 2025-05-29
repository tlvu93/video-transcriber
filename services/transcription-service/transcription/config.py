import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = os.path.join(BASE_DIR, "data")

# Video directories - default is a single directory, but can be overridden with VIDEO_DIRS env var
DEFAULT_VIDEO_DIR = os.path.join(DATA_DIR, "videos")
VIDEO_DIRS_ENV = os.environ.get("VIDEO_DIRS", "")
VIDEO_DIRS = (
    [dir.strip() for dir in VIDEO_DIRS_ENV.split(",")]
    if VIDEO_DIRS_ENV
    else [DEFAULT_VIDEO_DIR]
)

# For backward compatibility
VIDEO_DIR = DEFAULT_VIDEO_DIR

# API service
API_URL = os.environ.get("API_URL", "http://api:8000")
