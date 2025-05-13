"""
This module contains configuration settings for the video transcriber application.
Database-related configuration has been moved to the API service.
"""

import os
import sys
from pathlib import Path

# Add the API service to the Python path
api_path = str(Path(__file__).parent.parent.parent / "api-service")
if api_path not in sys.path:
    sys.path.insert(0, api_path)

# Base directories
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = os.path.join(BASE_DIR, "data")

# Video and transcription directories
VIDEO_DIR = os.path.join(DATA_DIR, "videos")
TRANSCRIPT_DIR = os.path.join(DATA_DIR, "transcriptions")
SUMMARY_DIR = os.path.join(DATA_DIR, "summaries")

# API service
API_URL = os.environ.get("API_URL", "http://api:8000")

# LLM settings
LLM_HOST = os.environ.get("LLM_HOST", "http://localhost:11434/api/generate")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-r1")

# Import database configuration from API service
from api.config import DB_PATH, DATABASE_URL
