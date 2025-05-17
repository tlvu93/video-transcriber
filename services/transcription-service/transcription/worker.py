import os
import logging
import subprocess
import time
import requests
from typing import Dict, Any, Tuple, Optional

from transcription.config import VIDEO_DIR, TRANSCRIPT_DIR, API_URL

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('transcription.worker')

def get_video_from_api(video_id: str) -> Dict[str, Any]:
    """Get video details from API."""
    response = requests.get(f"{API_URL}/videos/{video_id}")
    response.raise_for_status()
    return response.json()

def create_transcript_api(video_id: str, content: str, format: str = "txt") -> Dict[str, Any]:
    """Create transcript via API."""
    data = {
        "video_id": video_id,
        "source_type": "video",
        "content": content,
        "format": format,
        "status": "completed"
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

def process_transcription_job(job_id: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Process a transcription job.
    
    Args:
        job_id: The ID of the transcription job to process
        
    Returns:
        Tuple of (success, error_details)
    """
    try:
        # Get job details from API
        response = requests.get(f"{API_URL}/transcription-jobs/{job_id}")
        response.raise_for_status()
        job = response.json()
        video_id = job["video_id"]
        
        # Get the video from API
        video = get_video_from_api(video_id)
        if not video:
            return False, {"error": f"Video not found: {video_id}"}
        
        # Get the video file path
        video_path = os.path.join(VIDEO_DIR, video["filename"])
        if not os.path.exists(video_path):
            return False, {"error": f"Video file not found: {video_path}"}
        
        # Create transcript file path

        
        # Extract audio from video
        logger.info(f"Extracting audio from video: {video_path}")
        audio_path = extract_audio(video_path)
        
        # Transcribe audio
        logger.info(f"Transcribing audio: {audio_path}")
        transcript_text = transcribe_audio(audio_path)
        
        # Clean up temporary audio file
        if os.path.exists(audio_path):
            os.remove(audio_path)
        
        # Create transcript record via API
        transcript = create_transcript_api(video_id, transcript_text)
        
        # Update video status via API
        update_video_status_api(video_id, "transcribed")
        
        # Create summarization job via API
        data = {"transcript_id": transcript["id"]}
        response = requests.post(f"{API_URL}/summarization-jobs/", json=data)
        response.raise_for_status()
        
        return True, None
        
    except Exception as e:
        logger.exception(f"Error processing transcription job: {str(e)}")
        return False, {"error": str(e), "type": type(e).__name__}

def extract_audio(video_path: str) -> str:
    """
    Extract audio from a video file.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        Path to the extracted audio file
    """
    # Create temporary audio file path
    audio_path = f"{os.path.splitext(video_path)[0]}.wav"
    
    # Extract audio using ffmpeg
    subprocess.run([
        "ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", audio_path
    ], check=True)
    
    return audio_path

def transcribe_audio(audio_path: str) -> str:
    """
    Transcribe an audio file.
    
    Args:
        audio_path: Path to the audio file
        
    Returns:
        Transcription text
    """
    # In a real implementation, this would use a speech recognition model
    # For now, we'll just return a placeholder
    logger.info(f"Transcribing audio file: {audio_path}")
    
    # Simulate processing time
    time.sleep(2)
    
    # Return placeholder text
    return f"This is a placeholder transcript for {os.path.basename(audio_path)}.\n\nIn a real implementation, this would be the actual transcription of the audio content."
