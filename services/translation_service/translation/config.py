import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = os.path.join(BASE_DIR, "data")

# Video and transcription directories
VIDEO_DIR = os.path.join(DATA_DIR, "videos")

# API service
API_URL = os.environ.get("API_URL", "http://api:8000")

# LLM settings
LLM_HOST = os.environ.get("LLM_HOST", "http://localhost:11434/api/generate")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-r1")

# Supported languages
SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish", 
    "fr": "French",
    "de": "German",
    "ja": "Japanese",
}
