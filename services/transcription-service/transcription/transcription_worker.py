import time
import logging
import os
import whisper
import traceback
import requests
from datetime import datetime
from typing import Optional, Dict, Any, List

import sys
from pathlib import Path

# Add the project root directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from transcription.config import VIDEO_DIR, API_URL
from transcription.processor import (
    create_transcript_api,
    update_job_status_api
)
from common.messaging import (
    RabbitMQClient, 
    publish_transcription_created_event,
    publish_job_status_changed_event
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('transcription_worker')

# Initialize RabbitMQ client
rabbitmq_client = RabbitMQClient()

# Global model instance
model = None

def load_whisper_model():
    """Load the Whisper model."""
    global model
    if model is None:
        logger.info("Loading Whisper model...")
        model = whisper.load_model("base")
        logger.info("Whisper model loaded successfully")
    return model

def format_srt_timestamp(seconds):
    """Format seconds as SRT timestamp."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def get_job_from_api(job_id: str) -> Dict[str, Any]:
    """Get job details from API."""
    response = requests.get(f"{API_URL}/transcription-jobs/{job_id}")
    response.raise_for_status()
    return response.json()

def get_video_from_api(video_id: str) -> Dict[str, Any]:
    """Get video details from API."""
    response = requests.get(f"{API_URL}/videos/{video_id}")
    response.raise_for_status()
    return response.json()

def update_video_status_api(video_id: str, status: str) -> None:
    """Update video status via API."""
    data = {"status": status}
    response = requests.patch(f"{API_URL}/videos/{video_id}", json=data)
    response.raise_for_status()
    logger.info(f"Video {video_id} status updated to {status}")

def process_transcription_job(job_id: str) -> bool:
    """
    Process a transcription job.
    
    Args:
        job_id: The ID of the transcription job to process
        
    Returns:
        True if the job was processed successfully, False otherwise
    """
    start_time = time.time()
    
    try:
        # Get job details
        job = get_job_from_api(job_id)
        video_id = job["video_id"]
        
        # Mark job as started
        update_job_status_api(job_id, "processing")
        
        # Get video details
        video = get_video_from_api(video_id)
        
        # Get video file path
        filepath = os.path.join("/app/data/videos", video["filename"])
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Video file not found: {filepath}")
        
        # Load Whisper model
        whisper_model = load_whisper_model()
        
        # Transcribe video
        logger.info(f"Transcribing video: {video['filename']}")
        result = whisper_model.transcribe(filepath, verbose=False)
        transcript_text = result["text"]
        logger.info(f"Transcription completed, length: {len(transcript_text)} characters")
        
        # Create transcript via API
        segments = result.get("segments", None)
        
        # Format segments for database storage if they exist
        formatted_segments = None
        if segments:
            formatted_segments = []
            for i, seg in enumerate(segments):
                formatted_segments.append({
                    "id": i + 1,
                    "start_time": seg["start"],
                    "end_time": seg["end"],
                    "text": seg["text"].strip()
                })
        
        transcript = create_transcript_api(video_id, transcript_text, formatted_segments)

        # Update video status
        update_video_status_api(video_id, "transcribed")
        
        # Mark job as completed
        processing_time = time.time() - start_time
        update_job_status_api(job_id, "completed", processing_time)
        
        logger.info(f"Transcription completed for video {video['filename']} in {processing_time:.2f} seconds")
        return True
        
    except Exception as e:
        logger.error(f"Error processing transcription job {job_id}: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        
        # Mark job as failed
        error_details = {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        try:
            update_job_status_api(job_id, "failed", error_details=error_details)
        except Exception as mark_error:
            logger.error(f"Error marking job as failed: {str(mark_error)}")
        
        # Update video status if it exists
        if 'video_id' in locals() and 'video' in locals():
            try:
                update_video_status_api(video_id, "error")
            except Exception as update_error:
                logger.error(f"Error updating video status: {str(update_error)}")
        
        return False

def get_next_transcription_job_api():
    """Get the next pending transcription job from the API."""
    try:
        response = requests.get(f"{API_URL}/transcription-jobs/next")
        if response.status_code == 404:
            # No pending jobs
            return None
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting next transcription job: {str(e)}")
        return None
