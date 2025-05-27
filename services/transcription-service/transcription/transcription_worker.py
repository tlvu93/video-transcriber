import time
import logging
import os
import whisperx
import traceback
import requests
import threading
import torch
import gc
from datetime import datetime
from typing import Optional, Dict, Any, List

import sys
from pathlib import Path

# Add the project root directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from transcription.config import VIDEO_DIR, VIDEO_DIRS, API_URL
from transcription.processor import (
    create_transcript_api,
    update_job_status_api
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('transcription_worker')

# Global model instances and lock - singleton pattern
_model = None
_device = None
_model_lock = threading.Lock()
_model_loaded = False

def get_whisperx_model():
    """Get the singleton WhisperX model instance."""
    global _model, _device, _model_loaded
    
    with _model_lock:
        if not _model_loaded:
            # Determine device for processing
            _device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {_device}")
            
            logger.info("Loading WhisperX model...")
            try:
                # Use a more compatible approach for loading WhisperX model
                _model = whisperx.load_model(
                    "large-v2", 
                    _device, 
                    compute_type="float16" if _device == "cuda" else "int8",
                    language="auto"  # Explicitly set language parameter
                )
                _model_loaded = True
                logger.info("WhisperX model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load WhisperX model: {str(e)}")
                # Try with a simpler model configuration as fallback
                try:
                    logger.info("Trying fallback model configuration...")
                    _model = whisperx.load_model("base", _device)
                    _model_loaded = True
                    logger.info("WhisperX fallback model loaded successfully")
                except Exception as fallback_error:
                    logger.error(f"Fallback model also failed: {str(fallback_error)}")
                    raise e
        
        return _model, _device

def format_srt_timestamp(seconds):
    """Format seconds as SRT timestamp."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def get_job_from_api(job_id: str) -> Dict[str, Any]:
    """Get job details from API."""
    try:
        response = requests.get(f"{API_URL}/transcription-jobs/{job_id}", timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting job from API: {str(e)}")
        raise

def get_video_from_api(video_id: str) -> Dict[str, Any]:
    """Get video details from API."""
    try:
        response = requests.get(f"{API_URL}/videos/{video_id}", timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting video from API: {str(e)}")
        raise

def update_video_status_api(video_id: str, status: str) -> None:
    """Update video status via API."""
    try:
        data = {"status": status}
        response = requests.patch(f"{API_URL}/videos/{video_id}", json=data, timeout=30)
        response.raise_for_status()
        logger.info(f"Video {video_id} status updated to {status}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating video status: {str(e)}")
        raise

def find_video_file(filename: str) -> str:
    """Find video file in configured directories."""
    # First try the default path
    filepath = os.path.join("/app/data/videos", filename)
    
    if os.path.exists(filepath):
        return filepath
    
    # If file doesn't exist at the expected path, search in all video directories
    logger.info(f"Video file not found at {filepath}, searching in all video directories...")
    
    # Search in all configured video directories
    for video_dir in VIDEO_DIRS:
        # First check directly in the video directory
        test_path = os.path.join(video_dir, filename)
        if os.path.exists(test_path):
            logger.info(f"Found video file at: {test_path}")
            return test_path
        
        # Then search in subdirectories
        for root, _, files in os.walk(video_dir):
            if filename in files:
                found_path = os.path.join(root, filename)
                logger.info(f"Found video file at: {found_path}")
                return found_path
    
    raise FileNotFoundError(f"Video file not found: {filename}")

def transcribe_with_whisperx(filepath: str) -> tuple[str, List[Dict]]:
    """Transcribe video file using WhisperX."""
    model, device = get_whisperx_model()
    
    # Use a lock to ensure only one thread uses the model at a time
    with _model_lock:
        logger.info("Starting WhisperX transcription...")
        
        try:
            # Load audio
            audio = whisperx.load_audio(filepath)
            
            # Transcribe with WhisperX
            result = model.transcribe(audio, batch_size=16)
            transcript_text = result["text"]
            logger.info(f"Initial transcription completed, length: {len(transcript_text)} characters")
            
            # Align timestamps for better accuracy
            logger.info("Aligning timestamps...")
            model_a, metadata_align = whisperx.load_align_model(
                language_code=result["language"], 
                device=device
            )
            result = whisperx.align(
                result["segments"], 
                model_a, 
                metadata_align, 
                audio, 
                device, 
                return_char_alignments=False
            )
            logger.info("Timestamp alignment completed")
            
            # Perform speaker diarization
            logger.info("Performing speaker diarization...")
            try:
                # Use local diarization without HuggingFace token
                diarize_model = whisperx.DiarizationPipeline(use_auth_token=None, device=device)
                diarize_segments = diarize_model(audio)
                
                # Assign speakers to segments
                result = whisperx.assign_word_speakers(diarize_segments, result)
                logger.info("Speaker diarization completed")
            except Exception as diarize_error:
                logger.warning(f"Speaker diarization failed: {str(diarize_error)}")
                logger.info("Continuing without speaker diarization")
            
            # Clean up audio data to free memory
            del audio
            gc.collect()
            
            logger.info(f"WhisperX transcription completed, length: {len(transcript_text)} characters")
            
            return transcript_text, result.get("segments", [])
            
        except RuntimeError as e:
            if "cannot reshape tensor of 0 elements" in str(e):
                raise ValueError(f"Cannot process video file: {filepath}. The file may be corrupted or in an unsupported format.")
            else:
                raise
        except Exception as e:
            logger.error(f"Transcription error: {str(e)}")
            raise

def process_transcription_job(job_id: str) -> bool:
    """
    Process a transcription job.
    
    Args:
        job_id: The ID of the transcription job to process
        
    Returns:
        True if the job was processed successfully, False otherwise
    """
    start_time = time.time()
    video_id = None
    
    try:
        logger.info(f"Starting processing of transcription job {job_id}")
        
        # Get job details
        job = get_job_from_api(job_id)
        video_id = job["video_id"]
        
        # Mark job as started
        update_job_status_api(job_id, "processing")
        
        # Get video details
        video = get_video_from_api(video_id)
        filename = video["filename"]
        
        # Find video file
        filepath = find_video_file(filename)
        
        # Check file size
        file_size = os.path.getsize(filepath)
        if file_size == 0:
            raise ValueError(f"Video file is empty (0 bytes): {filepath}")
        
        logger.info(f"Processing video: {filename} (size: {file_size} bytes)")
        
        # Transcribe video with WhisperX
        transcript_text, segments = transcribe_with_whisperx(filepath)
        
        # Format segments for database storage if they exist
        formatted_segments = None
        if segments:
            formatted_segments = []
            for i, seg in enumerate(segments):
                segment_data = {
                    "id": i + 1,
                    "start_time": seg["start"],
                    "end_time": seg["end"],
                    "text": seg["text"].strip()
                }
                
                # Add speaker information if available
                if "speaker" in seg:
                    segment_data["speaker"] = seg["speaker"]
                
                formatted_segments.append(segment_data)
        
        # Create transcript via API
        transcript = create_transcript_api(video_id, transcript_text, formatted_segments)
        if not transcript:
            raise Exception("Failed to create transcript via API")

        # Update video status
        update_video_status_api(video_id, "transcribed")
        
        # Mark job as completed
        processing_time = time.time() - start_time
        update_job_status_api(job_id, "completed", processing_time)
        
        logger.info(f"Transcription completed for video {filename} in {processing_time:.2f} seconds")
        return True
        
    except Exception as e:
        logger.error(f"Error processing transcription job {job_id}: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        
        # Mark job as failed
        error_details = {
            "error": str(e),
            "traceback": traceback.format_exc()[:1000]  # Limit traceback size
        }
        
        try:
            update_job_status_api(job_id, "failed", error_details=error_details)
        except Exception as mark_error:
            logger.error(f"Error marking job as failed: {str(mark_error)}")
        
        # Update video status if it exists
        if video_id:
            try:
                update_video_status_api(video_id, "error")
            except Exception as update_error:
                logger.error(f"Error updating video status: {str(update_error)}")
        
        return False
    finally:
        # Force garbage collection to free memory
        gc.collect()
