import gc
import logging
import os
import subprocess
import threading
import time
import traceback
from typing import Dict, List, Optional, Tuple

import torch
import whisperx
from transcription.api_client import (
    create_transcript_api,
    get_job_from_api,
    get_video_from_api,
    update_job_status_api,
    update_video_status_api,
)
from transcription.config import VIDEO_DIRS

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("transcription_worker")

# Global model and device
_model = None
_device = None
_model_lock = threading.Lock()


def get_whisperx_model():
    """Get or initialize the WhisperX model."""
    global _model, _device

    with _model_lock:
        if _model is None:
            # Determine device
            _device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {_device}")

            # Select model size based on available memory
            model_name = "large"  # Default model size
            compute_type = "float16" if _device == "cuda" else "int8"

            # Try to load model with fallbacks
            try:
                # Clean memory before loading
                gc.collect()
                if _device == "cuda":
                    torch.cuda.empty_cache()

                _model = whisperx.load_model(
                    model_name, _device, compute_type=compute_type, device_index=0
                )
                logger.info(f"WhisperX model '{model_name}' loaded successfully")
            except Exception as e:
                # Fallback to smaller model if needed
                logger.warning(f"Failed to load model '{model_name}': {str(e)}")
                try:
                    model_name = "small"
                    _model = whisperx.load_model(
                        model_name, _device, compute_type=compute_type, device_index=0
                    )
                    logger.info(f"WhisperX model '{model_name}' loaded successfully")
                except Exception as e:
                    # Final fallback to tiny model
                    logger.warning(f"Failed to load model '{model_name}': {str(e)}")
                    model_name = "tiny"
                    compute_type = "int8"
                    _model = whisperx.load_model(
                        model_name, _device, compute_type=compute_type, device_index=0
                    )
                    logger.info(f"WhisperX model '{model_name}' loaded successfully")

        return _model, _device


def find_video_file(filename: str) -> str:
    """Find video file in configured directories."""
    # Check default path first
    default_path = os.path.join("/app/data/videos", filename)
    if os.path.exists(default_path):
        return default_path

    # Search in all video directories
    for video_dir in VIDEO_DIRS:
        # Create directory if it doesn't exist
        if not os.path.exists(video_dir):
            os.makedirs(video_dir, exist_ok=True)

        # Check direct path
        file_path = os.path.join(video_dir, filename)
        if os.path.exists(file_path):
            return file_path

        # Search in subdirectories
        for root, _, files in os.walk(video_dir):
            if filename in files:
                return os.path.join(root, filename)

    # Check if filename is a path
    if os.path.sep in filename:
        direct_path = (
            filename if os.path.isabs(filename) else os.path.join(os.getcwd(), filename)
        )
        if os.path.exists(direct_path):
            return direct_path

    raise FileNotFoundError(f"Video file not found: {filename}")


def extract_audio(video_path: str) -> str:
    """Extract audio from video file using ffmpeg."""
    audio_dir = os.path.dirname(video_path)
    audio_filename = f"temp_audio_{int(time.time())}.wav"
    audio_path = os.path.join(audio_dir, audio_filename)

    try:
        cmd = [
            "ffmpeg",
            "-i",
            video_path,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-y",
            audio_path,
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return audio_path
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg error: {e.stderr.decode('utf-8', errors='replace')}")
        raise ValueError(f"Failed to extract audio from video: {video_path}")
    except Exception as e:
        logger.error(f"Unexpected error during audio extraction: {str(e)}")
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception:
                pass
        raise


def extract_text_from_segments(segments: List[Dict]) -> str:
    """Extract and join text from segments."""
    if not segments:
        return ""

    # Log first segment for debugging
    if segments:
        logger.info(f"First segment structure: {segments[0]}")

    # Extract text from segments
    texts = []
    for seg in segments:
        if isinstance(seg, dict) and "text" in seg:
            texts.append(seg["text"].strip())

    # Join texts
    text = " ".join(texts)
    logger.info(
        f"Text key missing in result, constructed text from segments: {len(text)} characters"
    )
    return text


def get_whisperx_model_for_file(filepath: str):
    """Get appropriate WhisperX model based on file type and size."""
    global _model, _device

    # Check file extension
    file_ext = os.path.splitext(filepath)[1].lower()
    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)

    with _model_lock:
        # Determine device
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {_device}")

        # Select model size based on file type and size
        if file_ext == ".mov" and file_size_mb > 100:
            # For large .mov files, use a smaller model to avoid memory issues
            logger.info(
                f"Large .mov file detected ({file_size_mb: .2f} MB), using smaller model"
            )
            model_name = "small"
        else:
            # Default model size
            model_name = "medium"

        compute_type = "float16" if _device == "cuda" else "int8"

        # Try to load model with fallbacks
        try:
            # Clean memory before loading
            gc.collect()
            if _device == "cuda":
                torch.cuda.empty_cache()

            _model = whisperx.load_model(
                model_name, _device, compute_type=compute_type, device_index=0
            )
            logger.info(f"WhisperX model '{model_name}' loaded successfully")
        except Exception as e:
            # Fallback to smaller model if needed
            logger.warning(f"Failed to load model '{model_name}': {str(e)}")
            try:
                model_name = "small"
                _model = whisperx.load_model(
                    model_name, _device, compute_type=compute_type, device_index=0
                )
                logger.info(f"WhisperX model '{model_name}' loaded successfully")
            except Exception as e:
                # Final fallback to tiny model
                logger.warning(f"Failed to load model '{model_name}': {str(e)}")
                model_name = "tiny"
                compute_type = "int8"
                _model = whisperx.load_model(
                    model_name, _device, compute_type=compute_type, device_index=0
                )
                logger.info(f"WhisperX model '{model_name}' loaded successfully")

        return _model, _device


def transcribe_with_whisperx(filepath: str) -> Tuple[str, List[Dict]]:
    """Transcribe audio/video file using WhisperX."""
    audio_path = None

    try:
        # Extract audio if needed
        file_ext = os.path.splitext(filepath)[1].lower()
        video_extensions = [
            ".mp4",
            ".avi",
            ".mov",
            ".mkv",
            ".webm",
            ".flv",
            ".wmv",
            ".m4v",
        ]

        if file_ext in video_extensions:
            audio_path = extract_audio(filepath)
            filepath_to_process = audio_path
        else:
            filepath_to_process = filepath

        # Get appropriate model based on file type
        model, device = get_whisperx_model_for_file(filepath)

        # Transcribe with WhisperX
        with _model_lock:
            # Load audio with memory management
            try:
                # Force garbage collection before loading audio
                gc.collect()
                if device == "cuda":
                    torch.cuda.empty_cache()

                audio = whisperx.load_audio(filepath_to_process)
                if len(audio) == 0:
                    raise ValueError(
                        f"Audio file is empty or invalid: {filepath_to_process}"
                    )
            except Exception as e:
                logger.error(f"Error loading audio: {str(e)}")
                raise ValueError(f"Failed to load audio: {str(e)}")

            # Transcribe with memory-optimized batch size
            # Use smaller batch size for .mov files to reduce memory usage
            batch_size = 8 if file_ext == ".mov" else 16
            logger.info(f"Transcribing with batch size: {batch_size}")

            result = model.transcribe(
                audio,
                batch_size=batch_size,
                language=None,  # Auto-detect language
                task="transcribe",
            )

            # Extract text from result
            transcript_text = ""
            if "text" not in result:
                # Handle missing text key by constructing from segments
                if "segments" in result and result["segments"]:
                    transcript_text = extract_text_from_segments(result["segments"])
                    if not transcript_text:
                        raise ValueError("Could not extract text from segments")
                else:
                    logger.error(
                        "WhisperX result missing both 'text' and 'segments' keys"
                    )
                    raise ValueError("Transcription result is missing required data")
            else:
                transcript_text = result["text"]

            logger.info(
                f"Initial transcription completed, length: {len(transcript_text)} characters"
            )

            # Skip further processing for short transcripts
            if len(transcript_text.strip()) < 10:
                logger.warning(
                    "Transcript is very short, skipping alignment and diarization"
                )
                return transcript_text, result.get("segments", [])

            # Try to align timestamps
            try:
                logger.info("Aligning timestamps...")
                model_a, metadata_align = whisperx.load_align_model(
                    language_code=result["language"], device=device
                )
                result = whisperx.align(
                    result["segments"],
                    model_a,
                    metadata_align,
                    audio,
                    device,
                    return_char_alignments=False,
                )
            except Exception as e:
                logger.warning(f"Timestamp alignment failed: {str(e)}")

            # Try speaker diarization
            try:
                logger.info("Performing speaker diarization...")
                diarize_model = whisperx.DiarizationPipeline(
                    use_auth_token=None, device=device
                )
                diarize_segments = diarize_model(audio)
                result = whisperx.assign_word_speakers(diarize_segments, result)
            except Exception as e:
                logger.warning(f"Speaker diarization failed: {str(e)}")

            # Clean up memory
            del audio
            gc.collect()

            return transcript_text, result.get("segments", [])

    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        raise
    finally:
        # Clean up temporary audio file
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception:
                pass


def format_segments(segments: List[Dict]) -> Optional[List[Dict]]:
    """Format segments for database storage."""
    if not segments:
        return None

    formatted_segments = []
    for i, seg in enumerate(segments):
        # Skip invalid segments
        if not isinstance(seg, dict):
            continue

        # Check for required keys
        if "start" not in seg or "end" not in seg or "text" not in seg:
            continue

        try:
            segment_data = {
                "id": i + 1,
                "start_time": float(seg["start"]),
                "end_time": float(seg["end"]),
                "text": seg["text"].strip(),
            }

            # Add speaker information if available
            if "speaker" in seg:
                segment_data["speaker"] = seg["speaker"]

            formatted_segments.append(segment_data)
        except (ValueError, TypeError):
            continue

    return formatted_segments


def process_transcription_job(job_id: str) -> bool:
    """Process a transcription job."""
    start_time = time.time()
    video_id = None

    try:
        logger.info(f"Starting processing of transcription job {job_id}")

        # Get job and video details
        job = get_job_from_api(job_id)
        video_id = job["video_id"]
        update_job_status_api(job_id, "processing")

        video = get_video_from_api(video_id)
        filename = video["filename"]

        # Find and validate video file
        filepath = find_video_file(filename)
        if os.path.getsize(filepath) == 0:
            raise ValueError(f"Video file is empty (0 bytes): {filepath}")

        # Transcribe video
        transcript_text, segments = transcribe_with_whisperx(filepath)

        # Format segments and create transcript
        formatted_segments = format_segments(segments)
        transcript = create_transcript_api(
            video_id, transcript_text, formatted_segments
        )
        if not transcript:
            raise Exception("Failed to create transcript via API")

        # Update statuses
        update_video_status_api(video_id, "transcribed")
        processing_time = time.time() - start_time
        update_job_status_api(job_id, "completed", processing_time)

        logger.info(
            f"Transcription completed for video {filename} in {processing_time: .2f} seconds"
        )
        return True

    except Exception as e:
        logger.error(f"Error processing transcription job {job_id}: {str(e)}")

        # Mark job as failed
        error_details = {"error": str(e), "traceback": traceback.format_exc()[:1000]}

        try:
            update_job_status_api(job_id, "failed", error_details=error_details)
        except Exception:
            pass

        # Update video status if it exists
        if video_id:
            try:
                update_video_status_api(video_id, "error")
            except Exception:
                pass

        return False
    finally:
        # Force garbage collection
        gc.collect()
