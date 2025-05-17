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

from transcription.config import VIDEO_DIR, TRANSCRIPT_DIR, API_URL

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('transcription_worker')

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

def mark_job_started_api(job_id: str) -> None:
    """Mark job as started via API."""
    response = requests.post(f"{API_URL}/transcription-jobs/{job_id}/start")
    response.raise_for_status()
    logger.info(f"Job {job_id} marked as started")

def mark_job_completed_api(job_id: str, processing_time: float) -> None:
    """Mark job as completed via API."""
    data = {"processing_time_seconds": processing_time}
    response = requests.post(f"{API_URL}/transcription-jobs/{job_id}/complete", json=data)
    response.raise_for_status()
    logger.info(f"Job {job_id} marked as completed in {processing_time:.2f} seconds")

def mark_job_failed_api(job_id: str, error_details: Dict[str, Any]) -> None:
    """Mark job as failed via API."""
    response = requests.post(f"{API_URL}/transcription-jobs/{job_id}/fail", json={"error_details": error_details})
    response.raise_for_status()
    logger.info(f"Job {job_id} marked as failed: {error_details}")

def create_transcript_api(video_id: str, content: str, segments: Optional[List[Dict[str, Any]]] = None, format: str = "txt") -> Dict[str, Any]:
    """Create transcript via API."""
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
    
    data = {
        "video_id": video_id,
        "source_type": "video",
        "content": content,
        "format": format,
        "status": "completed",
        "segments": formatted_segments
    }
    response = requests.post(f"{API_URL}/transcripts/", json=data)
    response.raise_for_status()
    return response.json()

def update_video_status_api(video_id: str, status: str) -> None:
    """Update video status via API."""
    data = {"status": status}
    response = requests.patch(f"{API_URL}/videos/{video_id}", json=data)
    response.raise_for_status()
    logger.info(f"Video {video_id} status updated to {status}")

def create_summarization_job_api(transcript_id: str) -> Dict[str, Any]:
    """Create summarization job via API."""
    data = {"transcript_id": transcript_id}
    response = requests.post(f"{API_URL}/summarization-jobs/", json=data)
    response.raise_for_status()
    return response.json()

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
        mark_job_started_api(job_id)
        
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
        transcript = create_transcript_api(video_id, transcript_text, segments, "srt")
        
        # Save SRT if available
        if "segments" in result:
            # Save SRT to file system
            os.makedirs("/app/data/transcriptions", exist_ok=True)
            basename = os.path.splitext(video["filename"])[0]
            srt_path = os.path.join("/app/data/transcriptions", f"{basename}.srt")
            with open(srt_path, "w", encoding="utf-8") as f:
                for i, seg in enumerate(result["segments"]):
                    f.write(f"{i+1}\n")
                    f.write(f"{format_srt_timestamp(seg['start'])} --> {format_srt_timestamp(seg['end'])}\n")
                    f.write(f"{seg['text'].strip()}\n\n")
            logger.info(f"SRT file saved to: {srt_path}")
            
            # Also save plain text transcript
            txt_path = os.path.join("/app/data/transcriptions", f"{basename}.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(transcript_text)
            logger.info(f"Transcript saved to: {txt_path}")
        
        # Update video status
        update_video_status_api(video_id, "transcribed")
        
        # Create summarization job
        create_summarization_job_api(transcript["id"])
        
        # Mark job as completed
        processing_time = time.time() - start_time
        mark_job_completed_api(job_id, processing_time)
        
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
            mark_job_failed_api(job_id, error_details)
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

def start_worker(poll_interval: int = 5):
    """
    Start the transcription worker.
    
    Args:
        poll_interval: Time in seconds to wait between polling for new jobs
    """
    logger.info("Starting transcription worker")
    
    # Load Whisper model at startup
    load_whisper_model()
    
    while True:
        try:
            # Get next job from API
            job = get_next_transcription_job_api()
            
            if job:
                logger.info(f"Processing transcription job {job['id']} for video {job['video_id']}")
                process_transcription_job(job['id'])
            else:
                logger.debug("No pending transcription jobs")
            
            # Wait before checking for new jobs
            time.sleep(poll_interval)
            
        except Exception as e:
            logger.error(f"Error in transcription worker: {str(e)}")
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            time.sleep(poll_interval)

if __name__ == "__main__":
    start_worker()
