import os

from backend.app.runtime.bootstrap import get_app_data_dir, get_repo_root

# Base directories
BASE_DIR = get_repo_root()
DATA_DIR = str(get_app_data_dir())

# Video directories - default is a single directory, but can be overridden with VIDEO_DIRS env var
DEFAULT_VIDEO_DIR = os.path.join(DATA_DIR, "videos")
VIDEO_DIRS_ENV = os.environ.get("VIDEO_DIRS", "")
VIDEO_DIRS = [dir.strip() for dir in VIDEO_DIRS_ENV.split(",")] if VIDEO_DIRS_ENV else [DEFAULT_VIDEO_DIR]

# For backward compatibility
VIDEO_DIR = DEFAULT_VIDEO_DIR

FILE_STABILITY_CHECK_INTERVAL_SECONDS = int(os.environ.get("FILE_STABILITY_CHECK_INTERVAL_SECONDS", "5"))
FILE_STABILITY_REQUIRED_CHECKS = int(os.environ.get("FILE_STABILITY_REQUIRED_CHECKS", "3"))
FILE_STABILITY_MAX_WAIT_SECONDS = int(os.environ.get("FILE_STABILITY_MAX_WAIT_SECONDS", "300"))
