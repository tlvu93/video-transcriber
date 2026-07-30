import contextlib
import gc
import logging
import os
import subprocess
import threading
import time
import traceback
from contextlib import contextmanager
from datetime import datetime

import torch
import whisperx

from backend.app.domain.jobs import JobCancellationRequestedError
from backend.app.domain.records import resolve_video_storage_path
from backend.app.runtime.metrics import record_metric_event
from backend.app.transcription.api_client import (
    complete_transcription_job_api,
    create_transcript_api,
    ensure_transcription_job_not_cancelled_api,
    fail_transcription_job_api,
    get_job_from_api,
    get_video_from_api,
    update_transcription_job_progress_api,
    update_video_status_api,
)
from backend.app.transcription.config import (
    HF_TOKEN,
    WHISPERX_COMPUTE_TYPE,
    WHISPERX_ENABLE_ALIGNMENT,
    WHISPERX_ENABLE_DIARIZATION,
    WHISPERX_MODEL_NAME,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("transcription_worker")

# Global model and device
_model = None
_device = None
_model_lock = threading.Lock()


@contextmanager
def torch_load_compatibility_mode():
    """Keep third-party pyannote checkpoints working on newer PyTorch defaults."""
    original_torch_load = torch.load

    def compat_torch_load(*args, **kwargs):
        if kwargs.get("weights_only") is None:
            kwargs["weights_only"] = False
        return original_torch_load(*args, **kwargs)

    torch.load = compat_torch_load
    try:
        yield
    finally:
        torch.load = original_torch_load


def load_whisperx_model_with_fallback(
    preferred_model_name: str,
    device: str,
) -> tuple[object, str, str]:
    fallback_model_names = [preferred_model_name, "small", "tiny"]
    model_candidates = []
    for model_name in fallback_model_names:
        if model_name and model_name not in model_candidates:
            model_candidates.append(model_name)

    base_compute_type = WHISPERX_COMPUTE_TYPE or ("float16" if device == "cuda" else "int8")
    last_error: Exception | None = None

    for model_name in model_candidates:
        compute_type = WHISPERX_COMPUTE_TYPE or ("int8" if model_name == "tiny" else base_compute_type)

        try:
            gc.collect()
            if device == "cuda":
                torch.cuda.empty_cache()

            with torch_load_compatibility_mode():
                model = whisperx.load_model(model_name, device, compute_type=compute_type, device_index=0)
            logger.info(
                "WhisperX model '%s' loaded successfully with compute type '%s'",
                model_name,
                compute_type,
            )
            return model, model_name, compute_type
        except Exception as error:
            last_error = error
            logger.warning("Failed to load WhisperX model '%s': %s", model_name, error)

    assert last_error is not None
    raise last_error


def select_whisperx_model_name(filepath: str | None = None) -> str:
    if WHISPERX_MODEL_NAME:
        return WHISPERX_MODEL_NAME

    if filepath:
        file_ext = os.path.splitext(filepath)[1].lower()
        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        if file_ext == ".mov" and file_size_mb > 100:
            logger.info("Large .mov file detected (%.2f MB), preferring smaller WhisperX model", file_size_mb)
            return "small"

        return "medium"

    return "large"


def normalize_language_code(language_code: str) -> str:
    """
    Normalize language code to 2-letter ISO format.
    
    Args:
        language_code: Language code from WhisperX (could be 2 or 3 letters)
        
    Returns:
        Normalized 2-letter language code
    """
    if not language_code:
        return "en"
    
    # Convert to lowercase and strip whitespace
    lang = language_code.lower().strip()
    
    # Common language code mappings
    language_mappings = {
        # 3-letter to 2-letter ISO codes
        "eng": "en",
        "spa": "es", 
        "fre": "fr",
        "fra": "fr",
        "ger": "de",
        "deu": "de",
        "jpn": "ja",
        "chi": "zh",
        "zho": "zh",
        "ita": "it",
        "por": "pt",
        "rus": "ru",
        "ara": "ar",
        "hin": "hi",
        "kor": "ko",
        "nld": "nl",
        "swe": "sv",
        "nor": "no",
        "dan": "da",
        "fin": "fi",
        "pol": "pl",
        "ces": "cs",
        "hun": "hu",
        "tur": "tr",
        "heb": "he",
        "tha": "th",
        "vie": "vi",
        "ind": "id",
        "msa": "ms",
        "ukr": "uk",
        "bul": "bg",
        "hrv": "hr",
        "slv": "sl",
        "slk": "sk",
        "ron": "ro",
        "ell": "el",
        "lit": "lt",
        "lav": "lv",
        "est": "et",
        "mlt": "mt",
        "isl": "is",
        "gle": "ga",
        "cym": "cy",
        "eus": "eu",
        "cat": "ca",
        "glg": "gl",
    }
    
    # Check if it's already a 2-letter code
    if len(lang) == 2:
        return lang
    
    # Try to map 3-letter code to 2-letter
    if lang in language_mappings:
        normalized = language_mappings[lang]
        logger.info(f"Normalized language code '{language_code}' to '{normalized}'")
        return normalized
    
    # If we can't normalize, default to English
    logger.warning(f"Could not normalize language code '{language_code}', defaulting to 'en'")
    return "en"


def get_whisperx_model():
    """Get or initialize the WhisperX model."""
    global _model, _device

    with _model_lock:
        if _model is None:
            _device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {_device}")
            preferred_model_name = select_whisperx_model_name()
            logger.info("Preferring WhisperX model '%s'", preferred_model_name)
            _model, _, _ = load_whisperx_model_with_fallback(preferred_model_name, _device)

        return _model, _device


def find_video_file(filename: str, storage_path: str | None = None) -> str:
    """Resolve a video file from the canonical storage backend."""
    return resolve_video_storage_path(filename, storage_path=storage_path)


def coerce_datetime(raw_value: object) -> datetime | None:
    if isinstance(raw_value, datetime):
        return raw_value
    if isinstance(raw_value, str):
        candidate = raw_value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            return None
    return None


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
        subprocess.run(cmd, check=True, capture_output=True)
        return audio_path
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg error: {e.stderr.decode('utf-8', errors='replace')}")
        raise ValueError(f"Failed to extract audio from video: {video_path}") from e
    except Exception as e:
        logger.error(f"Unexpected error during audio extraction: {str(e)}")
        if os.path.exists(audio_path):
            with contextlib.suppress(Exception):
                os.remove(audio_path)
        raise


def extract_text_from_segments(segments: list[dict]) -> str:
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
    logger.info(f"Text key missing in result, constructed text from segments: {len(text)} characters")
    return text


def get_whisperx_model_for_file(filepath: str):
    """Get appropriate WhisperX model based on file type and size."""
    global _model, _device

    with _model_lock:
        _device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {_device}")
        preferred_model_name = select_whisperx_model_name(filepath)
        logger.info("Preferring WhisperX model '%s' for %s", preferred_model_name, os.path.basename(filepath))
        _model, _, _ = load_whisperx_model_with_fallback(preferred_model_name, _device)

        return _model, _device


def transcribe_with_whisperx(filepath: str) -> tuple[str, list[dict], str | None]:
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
                    raise ValueError(f"Audio file is empty or invalid: {filepath_to_process}")
            except Exception as e:
                logger.error(f"Error loading audio: {str(e)}")
                raise ValueError(f"Failed to load audio: {str(e)}") from e

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

            # Extract and normalize language from result
            language_code = result.get("language")
            if language_code:
                # Normalize language code to 2-letter ISO format
                language_code = normalize_language_code(language_code)
                logger.info(f"Detected language from WhisperX: {language_code}")
            else:
                logger.warning("No language detected by WhisperX, defaulting to 'en'")
                language_code = "en"

            # Extract text from result
            transcript_text = ""
            if "text" not in result:
                # Handle missing text key by constructing from segments
                if "segments" in result and result["segments"]:
                    transcript_text = extract_text_from_segments(result["segments"])
                    if not transcript_text:
                        raise ValueError("Could not extract text from segments")
                else:
                    logger.error("WhisperX result missing both 'text' and 'segments' keys")
                    raise ValueError("Transcription result is missing required data")
            else:
                transcript_text = result["text"]

            logger.info(f"Initial transcription completed, length: {len(transcript_text)} characters")

            # Skip further processing for short transcripts
            if len(transcript_text.strip()) < 10:
                logger.warning("Transcript is very short, skipping alignment and diarization")
                return transcript_text, result.get("segments", []), language_code

            # Try to align timestamps
            if WHISPERX_ENABLE_ALIGNMENT:
                try:
                    logger.info("Aligning timestamps...")
                    with torch_load_compatibility_mode():
                        model_a, metadata_align = whisperx.load_align_model(
                            language_code=result["language"],
                            device=device,
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
            else:
                logger.info("Timestamp alignment disabled via WHISPERX_ENABLE_ALIGNMENT")

            # Try speaker diarization
            try:
                if not WHISPERX_ENABLE_DIARIZATION:
                    logger.info("Speaker diarization disabled via WHISPERX_ENABLE_DIARIZATION")
                    raise ValueError("Speaker diarization disabled by configuration")
                if not HF_TOKEN:
                    logger.info("HF_TOKEN not configured, skipping speaker diarization")
                    raise ValueError("Speaker diarization disabled without HF_TOKEN")
                logger.info("Performing speaker diarization...")
                with torch_load_compatibility_mode():
                    diarize_model = whisperx.diarize.DiarizationPipeline(
                        use_auth_token=HF_TOKEN,
                        device=device,
                    )
                diarize_segments = diarize_model(audio)
                result = whisperx.assign_word_speakers(diarize_segments, result)

                # Log the number of speakers identified
                speakers = {s.get("speaker") for s in result["segments"] if "speaker" in s}
                logger.info(f"Speaker diarization completed. Identified {len(speakers)} speakers.")
            except Exception as e:
                logger.warning(f"Speaker diarization unavailable: {str(e)}")
                logger.debug("Speaker diarization traceback: %s", traceback.format_exc())

            # Clean up memory
            del audio
            gc.collect()

            return transcript_text, result.get("segments", []), language_code

    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        raise
    finally:
        # Clean up temporary audio file
        if audio_path and os.path.exists(audio_path):
            with contextlib.suppress(Exception):
                os.remove(audio_path)


def format_segments(segments: list[dict]) -> list[dict] | None:
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


def process_transcription_job(job_id: str, worker_id: str) -> bool:
    """Process a transcription job."""
    start_time = time.time()
    transcript_created = False
    video_id = None
    language_code = None
    video_created_at: datetime | None = None

    try:
        logger.info(f"Starting processing of transcription job {job_id}")

        # Get job and video details
        job = get_job_from_api(job_id)
        video_id = job["video_id"]
        update_transcription_job_progress_api(job_id, worker_id, 0.05)
        ensure_transcription_job_not_cancelled_api(job_id, worker_id)

        video = get_video_from_api(video_id)
        filename = video["filename"]
        video_created_at = coerce_datetime(video.get("created_at"))
        update_video_status_api(video_id, "processing")
        update_transcription_job_progress_api(job_id, worker_id, 0.1)
        ensure_transcription_job_not_cancelled_api(job_id, worker_id)

        # Prefer the canonical storage path and only fall back to legacy directory scans.
        filepath = find_video_file(filename, video.get("storage_path"))
        if os.path.getsize(filepath) == 0:
            raise ValueError(f"Video file is empty (0 bytes): {filepath}")

        # Transcribe video
        transcript_text, segments, language_code = transcribe_with_whisperx(filepath)
        update_transcription_job_progress_api(job_id, worker_id, 0.7)
        ensure_transcription_job_not_cancelled_api(job_id, worker_id)

        # Format segments and create transcript
        formatted_segments = format_segments(segments)
        
        transcript = create_transcript_api(video_id, transcript_text, formatted_segments, language_code)
        if not transcript:
            raise Exception("Failed to create transcript via API")
        transcript_created = True
        update_transcription_job_progress_api(job_id, worker_id, 0.9)
        ensure_transcription_job_not_cancelled_api(job_id, worker_id)

        # Update statuses
        update_video_status_api(video_id, "transcribed")
        update_transcription_job_progress_api(job_id, worker_id, 0.98)
        processing_time = time.time() - start_time
        complete_transcription_job_api(job_id, worker_id, processing_time)
        record_metric_event(
            "transcription_time_seconds",
            processing_time,
            source="transcription_worker",
            labels={"language_code": language_code or "unknown"},
        )
        if video_created_at is not None:
            record_metric_event(
                "ingest_latency_seconds",
                max((datetime.utcnow() - video_created_at).total_seconds(), 0.0),
                source="transcription_worker",
                labels={"status": "completed"},
            )

        logger.info(f"Transcription completed for video {filename} in {processing_time: .2f} seconds")
        return True

    except JobCancellationRequestedError:
        logger.info("Cancellation requested for transcription job %s", job_id)
        processing_time = time.time() - start_time
        with contextlib.suppress(Exception):
            complete_transcription_job_api(
                job_id,
                worker_id,
                processing_time,
                error_details={"error": "Job cancelled by request"},
            )

        if video_id:
            with contextlib.suppress(Exception):
                update_video_status_api(
                    video_id,
                    "transcribed" if transcript_created else "pending",
                )

        return False
    except Exception as e:
        logger.error(f"Error processing transcription job {job_id}: {str(e)}")

        # Mark job as failed
        error_details = {"error": str(e), "traceback": traceback.format_exc()[:1000]}

        with contextlib.suppress(Exception):
            fail_transcription_job_api(job_id, worker_id, error_details=error_details)

        # Update video status if it exists
        if video_id:
            with contextlib.suppress(Exception):
                update_video_status_api(video_id, "error")

        return False
    finally:
        # Force garbage collection
        gc.collect()
