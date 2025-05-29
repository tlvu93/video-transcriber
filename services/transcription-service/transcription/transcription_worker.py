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
            
            # Log available GPU memory if using CUDA
            if _device == "cuda":
                try:
                    free_memory, total_memory = torch.cuda.mem_get_info()
                    free_memory_gb = free_memory / (1024**3)
                    total_memory_gb = total_memory / (1024**3)
                    logger.info(f"GPU memory: {free_memory_gb:.2f}GB free / {total_memory_gb:.2f}GB total")
                except Exception as e:
                    logger.warning(f"Could not get GPU memory info: {str(e)}")
            
            # Try loading models in order of preference with fallbacks
            models_to_try = [
                {"name": "large-v2", "compute_type": "float16" if _device == "cuda" else "int8"},
                {"name": "medium", "compute_type": "float16" if _device == "cuda" else "int8"},
                {"name": "small", "compute_type": "float16" if _device == "cuda" else "int8"},
                {"name": "base", "compute_type": "float16" if _device == "cuda" else "int8"},
                {"name": "tiny", "compute_type": "int8"}  # Last resort
            ]
            
            last_error = None
            for model_config in models_to_try:
                try:
                    logger.info(f"Loading WhisperX model '{model_config['name']}' with compute_type={model_config['compute_type']}...")
                    
                    # Force garbage collection before loading model
                    gc.collect()
                    if _device == "cuda":
                        torch.cuda.empty_cache()
                    
                    _model = whisperx.load_model(
                        model_config["name"],
                        _device,
                        compute_type=model_config["compute_type"],
                        # language="de",
                        device_index=0  # Explicitly use first GPU if multiple are available
                    )
                    _model_loaded = True
                    logger.info(f"WhisperX model '{model_config['name']}' loaded successfully")
                    break
                except Exception as e:
                    last_error = e
                    error_msg = str(e)
                    logger.warning(f"Failed to load WhisperX model '{model_config['name']}': {error_msg}")
                    
                    # If out of memory, try to free up memory
                    if "CUDA out of memory" in error_msg or "device-side assert" in error_msg:
                        logger.info("CUDA out of memory detected, trying to free up memory...")
                        gc.collect()
                        if _device == "cuda":
                            torch.cuda.empty_cache()
            
            # If all models failed, raise the last error
            if not _model_loaded:
                logger.error("All WhisperX model configurations failed to load")
                if last_error:
                    raise RuntimeError(f"Failed to load any WhisperX model: {str(last_error)}") from last_error
                else:
                    raise RuntimeError("Failed to load any WhisperX model")
        
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
        logger.info(f"Found video file at default path: {filepath}")
        return filepath
    
    # If file doesn't exist at the expected path, search in all video directories
    logger.info(f"Video file not found at {filepath}, searching in all video directories...")
    
    # Log all configured video directories for debugging
    logger.info(f"Configured VIDEO_DIRS: {VIDEO_DIRS}")
    
    # Check if directories exist
    for video_dir in VIDEO_DIRS:
        if not os.path.exists(video_dir):
            logger.warning(f"Video directory does not exist: {video_dir}")
            try:
                os.makedirs(video_dir, exist_ok=True)
                logger.info(f"Created video directory: {video_dir}")
            except Exception as e:
                logger.error(f"Failed to create video directory {video_dir}: {str(e)}")
        else:
            logger.info(f"Video directory exists: {video_dir}")
    
    # Search in all configured video directories
    for video_dir in VIDEO_DIRS:
        # First check directly in the video directory
        test_path = os.path.join(video_dir, filename)
        if os.path.exists(test_path):
            logger.info(f"Found video file at: {test_path}")
            return test_path
        
        # Then search in subdirectories
        for root, dirs, files in os.walk(video_dir):
            logger.debug(f"Searching in directory: {root}, found files: {files}")
            if filename in files:
                found_path = os.path.join(root, filename)
                logger.info(f"Found video file at: {found_path}")
                return found_path
    
    # If still not found, check if the filename contains a path
    if os.path.sep in filename:
        direct_path = filename if os.path.isabs(filename) else os.path.join(os.getcwd(), filename)
        if os.path.exists(direct_path):
            logger.info(f"Found video file at direct path: {direct_path}")
            return direct_path
    
    error_msg = f"Video file not found: {filename}. Searched in directories: {VIDEO_DIRS}"
    logger.error(error_msg)
    raise FileNotFoundError(error_msg)

def extract_audio_from_video(video_path: str) -> str:
    """
    Extract audio from video file using ffmpeg.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        Path to the extracted audio file
    """
    # Create temporary audio file path with a unique name
    audio_dir = os.path.dirname(video_path)
    audio_filename = f"temp_audio_{os.path.basename(video_path)}_{int(time.time())}.wav"
    audio_path = os.path.join(audio_dir, audio_filename)
    
    logger.info(f"Extracting audio from video: {video_path} to {audio_path}")
    
    try:
        # Use subprocess to run ffmpeg
        import subprocess
        cmd = [
            "ffmpeg", 
            "-i", video_path, 
            "-vn",  # No video
            "-acodec", "pcm_s16le",  # PCM 16-bit little-endian format
            "-ar", "16000",  # 16kHz sample rate
            "-ac", "1",  # Mono
            "-y",  # Overwrite output file if it exists
            audio_path
        ]
        
        # Run ffmpeg
        process = subprocess.run(
            cmd, 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        
        logger.info(f"Audio extraction completed: {audio_path}")
        return audio_path
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error extracting audio with ffmpeg: {e}")
        logger.error(f"ffmpeg stderr: {e.stderr.decode('utf-8', errors='replace')}")
        raise ValueError(f"Failed to extract audio from video: {video_path}. The file may be corrupted or in an unsupported format.")
    except Exception as e:
        logger.error(f"Unexpected error during audio extraction: {str(e)}")
        raise

def transcribe_with_whisperx(filepath: str) -> tuple[str, List[Dict]]:
    """Transcribe video file using WhisperX."""
    model, device = get_whisperx_model()
    audio_path = None
    
    try:
        # Check if the file is a video file that needs audio extraction
        file_ext = os.path.splitext(filepath)[1].lower()
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v']
        
        if file_ext in video_extensions:
            logger.info(f"Detected video file format: {file_ext}")
            audio_path = extract_audio_from_video(filepath)
            filepath_to_process = audio_path
        else:
            # Assume it's already an audio file
            logger.info(f"Using file directly (assuming audio format): {filepath}")
            filepath_to_process = filepath
        
        # Use a lock to ensure only one thread uses the model at a time
        with _model_lock:
            logger.info("Starting WhisperX transcription...")
            
            try:
                # Load audio
                audio = whisperx.load_audio(filepath_to_process)
                
                # Check if audio is valid
                if len(audio) == 0:
                    raise ValueError(f"Audio file is empty or invalid: {filepath_to_process}")
                
                # Log audio properties
                logger.info(f"Audio loaded successfully: length={len(audio)} samples")
                
                # Transcribe with WhisperX
                result = model.transcribe(
                    audio, 
                    batch_size=16,
                    language=None,  # Auto-detect language
                    task="transcribe"
                )
                print(f"WhisperX transcription result: {result}")
                
                # Check if 'text' key exists in the result
                if "text" not in result:
                    # Log the keys that are present in the result for debugging
                    logger.warning(f"WhisperX result missing 'text' key. Available keys: {list(result.keys())}")
                    
                    # Try to construct text from segments if available
                    if "segments" in result and result["segments"]:
                        # Log the structure of the first segment for debugging
                        if result["segments"]:
                            logger.info(f"First segment structure: {result['segments'][0]}")
                        
                        # Safely extract text from segments, handling cases where segments might have unexpected structure
                        segment_texts = []
                        for seg in result["segments"]:
                            if isinstance(seg, dict):
                                segment_text = seg.get("text", "")
                                if segment_text:
                                    segment_texts.append(segment_text.strip())
                            else:
                                logger.warning(f"Unexpected segment format (not a dict): {type(seg)}")
                        
                        if segment_texts:
                            transcript_text = " ".join(segment_texts)
                            logger.info(f"Text key missing in result, constructed text from segments: {len(transcript_text)} characters")
                        else:
                            logger.error("Failed to extract any text from segments")
                            raise ValueError("Could not extract text from segments")
                    else:
                        # If no segments either, raise a more informative error
                        logger.error(f"WhisperX result missing both 'text' and usable 'segments' keys: {result.keys()}")
                        # Log the entire result structure for debugging (limiting size to avoid huge logs)
                        logger.error(f"WhisperX result structure: {str(result)[:1000]}")
                        raise ValueError("Transcription result is missing required 'text' field")
                else:
                    transcript_text = result["text"]
                
                logger.info(f"Initial transcription completed, length: {len(transcript_text)} characters")
                
                # Skip alignment and diarization for very short transcripts
                if len(transcript_text.strip()) < 10:
                    logger.warning("Transcript is very short, skipping alignment and diarization")
                    return transcript_text, result.get("segments", [])
                
                # Align timestamps for better accuracy
                try:
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
                except Exception as align_error:
                    logger.warning(f"Timestamp alignment failed: {str(align_error)}")
                    logger.info("Continuing with unaligned timestamps")
                
                # Perform speaker diarization
                try:
                    logger.info("Performing speaker diarization...")
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
                error_msg = str(e)
                if "cannot reshape tensor of 0 elements" in error_msg:
                    raise ValueError(f"Cannot process audio file: {filepath_to_process}. The file may be corrupted or in an unsupported format.")
                elif "CUDA out of memory" in error_msg:
                    raise ValueError(f"GPU ran out of memory while processing file: {filepath_to_process}. Try using a smaller model or increasing GPU memory.")
                else:
                    logger.error(f"Runtime error during transcription: {error_msg}")
                    raise
            except Exception as e:
                logger.error(f"Transcription error: {str(e)}")
                raise
    finally:
        # Clean up temporary audio file if it was created
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                logger.info(f"Removed temporary audio file: {audio_path}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary audio file {audio_path}: {str(e)}")

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
                # Skip segments with missing required keys
                if not isinstance(seg, dict):
                    logger.warning(f"Skipping non-dict segment: {seg}")
                    continue
                    
                # Check for required keys
                if "start" not in seg or "end" not in seg or "text" not in seg:
                    logger.warning(f"Skipping segment with missing required keys: {seg}")
                    continue
                
                try:
                    segment_data = {
                        "id": i + 1,
                        "start_time": float(seg["start"]),
                        "end_time": float(seg["end"]),
                        "text": seg["text"].strip()
                    }
                    
                    # Add speaker information if available
                    if "speaker" in seg:
                        segment_data["speaker"] = seg["speaker"]
                    
                    formatted_segments.append(segment_data)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error processing segment {i}: {str(e)}, segment data: {seg}")
        
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
