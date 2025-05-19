import whisper
import os
import sys
import logging
import traceback
import requests
import json
from pathlib import Path

# Add the project root directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from transcription.config import VIDEO_DIR, VIDEO_DIRS, API_URL
from transcription.utils import get_video_metadata
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
logger = logging.getLogger('processor')

# Initialize RabbitMQ client
rabbitmq_client = RabbitMQClient()

logger.info("Loading Whisper model...")
model = whisper.load_model("base")
logger.info("Whisper model loaded successfully")

os.makedirs(VIDEO_DIR, exist_ok=True)

logger.info(f"Video directory: {VIDEO_DIR}")

def create_transcript_api(video_id, content, segments=None):
    """Create a transcript via the API."""
    try:
        url = f"{API_URL}/transcripts/"
        data = {
            "video_id": video_id,
            "source_type": "video",
            "content": content,
            "format": "txt",
            "status": "completed",
            "segments": segments or []
        }
        
        response = requests.post(url, json=data)
        response.raise_for_status()
        
        transcript = response.json()
        logger.info(f"Created transcript {transcript['id']} for video {video_id}")
        
        # Create a summarization job for the transcript via API
        job_url = f"{API_URL}/summarization-jobs/"
        job_data = {
            "transcript_id": transcript['id']
        }
        
        job_response = requests.post(job_url, json=job_data)
        job_response.raise_for_status()
        
        job = job_response.json()
        logger.info(f"Created summarization job {job['id']} for transcript {transcript['id']} via API")
        
        # Publish transcript created event
        try:
            rabbitmq_client.connect()
            publish_transcription_created_event(
                rabbitmq_client, 
                str(transcript['id']), 
                str(video_id)
            )
            logger.info(f"Published transcription.created event for transcript {transcript['id']}")
        except Exception as e:
            logger.error(f"Error publishing event: {str(e)}")
            logger.info(f"Continuing with processing as summarization job was already created via API")
        
        return transcript
    
    except Exception as e:
        logger.error(f"Error creating transcript: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        return None

def update_job_status_api(job_id, status, processing_time=None, error_details=None):
    """Update the status of a transcription job via the API."""
    try:
        if status == "completed":
            url = f"{API_URL}/transcription-jobs/{job_id}/complete"
            data = {
                "status": status,
                "processing_time_seconds": processing_time
            }
        elif status == "failed":
            url = f"{API_URL}/transcription-jobs/{job_id}/fail"
            data = {
                "status": status,
                "error_details": error_details or {"error": "Unknown error"}
            }
        else:
            url = f"{API_URL}/transcription-jobs/{job_id}/start"
            data = {}
        
        response = requests.post(url, json=data)
        response.raise_for_status()
        
        job = response.json()
        logger.info(f"Updated transcription job {job_id} status to {status}")
        
        # Publish job status changed event
        try:
            rabbitmq_client.connect()
            publish_job_status_changed_event(
                rabbitmq_client, 
                "transcription", 
                str(job_id), 
                status
            )
            logger.info(f"Published job.status.changed event for job {job_id}")
        except Exception as e:
            logger.error(f"Error publishing event: {str(e)}")
        
        return job
    
    except Exception as e:
        logger.error(f"Error updating job status: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        return None

def process_video(filepath):
    logger.info(f"Processing video: {filepath}")
    try:
        # Check if file exists and is accessible
        if not os.path.exists(filepath):
            # If file doesn't exist at the expected path, try to find it in all video directories and their subdirectories
            filename = os.path.basename(filepath)
            logger.info(f"File not found at {filepath}, searching in all video directories for {filename}...")
            found = False
            
            # Search in all configured video directories
            for video_dir in VIDEO_DIRS:
                # First check directly in the video directory
                test_path = os.path.join(video_dir, filename)
                if os.path.exists(test_path):
                    filepath = test_path
                    logger.info(f"Found video file at: {filepath}")
                    found = True
                    break
                
                # Then search in subdirectories
                for root, _, files in os.walk(video_dir):
                    if filename in files:
                        filepath = os.path.join(root, filename)
                        logger.info(f"Found video file at: {filepath}")
                        found = True
                        break
                
                if found:
                    break
            
            if not found:
                logger.error(f"❌ File not found: {filename}")
                return None, None, None
            
        # Get video metadata
        try:
            logger.info(f"Getting metadata for: {os.path.basename(filepath)}")
            metadata = get_video_metadata(filepath)
            logger.info(f"Metadata retrieved successfully")
        except Exception as e:
            logger.error(f"⚠️ Error getting metadata: {str(e)}")
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            metadata = {"error": str(e)}
        
        logger.info(f"🔊 Transcribing: {os.path.basename(filepath)}")
        
        # Transcribe video
        try:
            logger.info("Starting Whisper transcription...")
            result = model.transcribe(filepath, verbose=False)
            transcript_text = result["text"]
            logger.info(f"Transcription completed, length: {len(transcript_text)} characters")
        except Exception as e:
            logger.error(f"❌ Transcription error: {str(e)}")
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            return None, metadata, None
        
        return transcript_text, metadata, None
        
    except Exception as e:
        logger.error(f"❌ Error processing video: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        return None, None, None

def format_srt_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"
