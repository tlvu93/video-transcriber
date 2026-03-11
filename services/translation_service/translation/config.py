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
LLM_REQUEST_TIMEOUT_SECONDS = int(os.environ.get("LLM_REQUEST_TIMEOUT_SECONDS", "900"))
OLLAMA_HEALTHCHECK_TTL_SECONDS = int(
    os.environ.get("OLLAMA_HEALTHCHECK_TTL_SECONDS", "60")
)
TRANSLATION_BATCH_SIZE = int(os.environ.get("TRANSLATION_BATCH_SIZE", "8"))
TRANSLATION_BATCH_MAX_CHARS = int(
    os.environ.get("TRANSLATION_BATCH_MAX_CHARS", "6000")
)
TRANSLATION_CACHE_DIR = os.environ.get(
    "TRANSLATION_CACHE_DIR",
    os.path.join(DATA_DIR, "translations"),
)

# Supported languages
SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish", 
    "fr": "French",
    "de": "German",
    "ja": "Japanese",
}
