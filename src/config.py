import os

VIDEO_DIR = "data/videos"
TRANSCRIPT_DIR = "data/transcriptions"
SUMMARY_DIR = "data/summaries"
DB_PATH = "data/db/processed_files.json"

# Self-hosted LLM settings
LLM_HOST = os.environ.get("LLM_HOST", "http://localhost:11434/api/generate")  # URL of the self-hosted LLM API
LLM_MODEL = os.environ.get("LLM_MODEL", "llama3")  # Model name to use for summarization
