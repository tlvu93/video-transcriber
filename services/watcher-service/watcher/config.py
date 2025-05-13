import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = os.path.join(BASE_DIR, "data")

# Video and transcription directories
VIDEO_DIR = os.path.join(DATA_DIR, "videos")
TRANSCRIPT_DIR = os.path.join(DATA_DIR, "transcriptions")
SUMMARY_DIR = os.path.join(DATA_DIR, "summaries")

# API service
API_URL = os.environ.get("API_URL", "http://api:8000")
