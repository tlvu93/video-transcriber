"""
This module provides job queue functions for the video transcriber application.
Database-related functionality has been moved to the API service.
This module re-exports the job queue functions from the API service.
"""

import sys
from pathlib import Path

# Add the API service to the Python path
api_path = str(Path(__file__).parent.parent.parent / "api-service")
if api_path not in sys.path:
    sys.path.insert(0, api_path)

# Re-export job queue functions from the API service
from api.job_queue import (
    get_next_transcription_job,
    get_next_summarization_job,
    mark_job_started,
    mark_job_completed,
    mark_job_failed,
    create_transcription_job,
    create_summarization_job
)
