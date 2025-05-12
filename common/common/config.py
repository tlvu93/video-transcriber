import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = os.path.join(BASE_DIR, "data")

# Video and transcription directories
VIDEO_DIR = os.path.join(DATA_DIR, "videos")
TRANSCRIPT_DIR = os.path.join(DATA_DIR, "transcriptions")
SUMMARY_DIR = os.path.join(DATA_DIR, "summaries")

# Database
DB_PATH = os.path.join(DATA_DIR, "db", "video_transcriber.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# LLM settings
LLM_HOST = os.environ.get("LLM_HOST", "http://localhost:11434/api/generate")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-r1")
