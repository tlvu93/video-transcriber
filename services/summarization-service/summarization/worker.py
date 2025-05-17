import os
import logging
import time
import requests
import traceback
from typing import Dict, Any, Tuple, Optional

from summarization.config import TRANSCRIPT_DIR, SUMMARY_DIR, API_URL
from summarization.summarizer import create_summary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('summarization.worker')

def get_job_from_api(job_id: str) -> Dict[str, Any]:
    """Get job details from API."""
    response = requests.get(f"{API_URL}/summarization-jobs/{job_id}")
    response.raise_for_status()
    return response.json()

def get_transcript_from_api(transcript_id: str) -> Dict[str, Any]:
    """Get transcript details from API."""
    response = requests.get(f"{API_URL}/transcripts/{transcript_id}")
    response.raise_for_status()
    return response.json()

def get_video_from_api(video_id: str) -> Dict[str, Any]:
    """Get video details from API."""
    response = requests.get(f"{API_URL}/videos/{video_id}")
    response.raise_for_status()
    return response.json()

def create_summary_api(transcript_id: str, content: str) -> Dict[str, Any]:
    """Create summary via API."""
    data = {
        "transcript_id": transcript_id,
        "content": content,
        "status": "completed"
    }
    response = requests.post(f"{API_URL}/summaries/", json=data)
    response.raise_for_status()
    return response.json()

def update_transcript_status_api(transcript_id: str, status: str) -> None:
    """Update transcript status via API."""
    data = {"status": status}
    response = requests.patch(f"{API_URL}/transcripts/{transcript_id}", json=data)
    response.raise_for_status()
    logger.info(f"Transcript {transcript_id} status updated to {status}")

def process_summarization_job(job_id: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Process a summarization job.
    
    Args:
        job_id: The ID of the summarization job to process
        
    Returns:
        Tuple of (success, error_details)
    """
    try:
        # Get job details from API
        job = get_job_from_api(job_id)
        transcript_id = job["transcript_id"]
        
        # Get the transcript from API
        transcript = get_transcript_from_api(transcript_id)
        if not transcript:
            return False, {"error": f"Transcript not found: {transcript_id}"}
        
        # Get the transcript content
        transcript_content = transcript["content"]
        
        # Generate summary
        logger.info(f"Generating summary for transcript: {transcript_id}")
        summary_text = create_summary(transcript_content, "manual_transcript")
        
        # Create summary record via API
        create_summary_api(transcript_id, summary_text)
        
        # Update transcript status via API
        update_transcript_status_api(transcript_id, "summarized")
        
        # Optionally save summary to file for backward compatibility
        if transcript["video_id"]:
            # Get the video filename
            video = get_video_from_api(transcript["video_id"])
            if video:
                summary_filename = f"{os.path.splitext(video['filename'])[0]}_summary.txt"
                summary_path = os.path.join(SUMMARY_DIR, summary_filename)
                
                # Ensure summary directory exists
                os.makedirs(SUMMARY_DIR, exist_ok=True)
                
                # Save summary to file
                with open(summary_path, "w", encoding="utf-8") as f:
                    f.write(summary_text)
                logger.info(f"Summary saved to file: {summary_path}")
        
        return True, None
        
    except Exception as e:
        logger.exception(f"Error processing summarization job: {str(e)}")
        return False, {"error": str(e), "type": type(e).__name__}
