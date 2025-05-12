import time
import logging
import os
import whisper
import traceback
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

import sys
from pathlib import Path

# Add the project root directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from common.common.database import get_db
from common.common.models import Video, Transcript, TranscriptionJob
from common.common.job_queue import get_next_transcription_job, mark_job_started, mark_job_completed, mark_job_failed, create_summarization_job

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

def process_transcription_job(job: TranscriptionJob, db: Session) -> bool:
    """
    Process a transcription job.
    
    Args:
        job: The transcription job to process
        db: Database session
        
    Returns:
        True if the job was processed successfully, False otherwise
    """
    start_time = time.time()
    
    try:
        # Mark job as started
        mark_job_started(job, db)
        
        # Get video
        video = db.query(Video).filter(Video.id == job.video_id).first()
        if not video:
            raise ValueError(f"Video {job.video_id} not found")
        
        # Get video file path
        filepath = os.path.join("data/videos", video.filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Video file not found: {filepath}")
        
        # Load Whisper model
        whisper_model = load_whisper_model()
        
        # Transcribe video
        logger.info(f"Transcribing video: {video.filename}")
        result = whisper_model.transcribe(filepath, verbose=False)
        transcript_text = result["text"]
        logger.info(f"Transcription completed, length: {len(transcript_text)} characters")
        
        # Create transcript
        transcript = Transcript(
            video_id=video.id,
            source_type="video",
            content=transcript_text,
            format="txt",
            status="completed"
        )
        db.add(transcript)
        db.commit()
        db.refresh(transcript)
        
        # Save SRT if available
        if "segments" in result:
            # Save SRT to file system
            os.makedirs("data/transcriptions", exist_ok=True)
            basename = os.path.splitext(video.filename)[0]
            srt_path = os.path.join("data/transcriptions", f"{basename}.srt")
            with open(srt_path, "w", encoding="utf-8") as f:
                for i, seg in enumerate(result["segments"]):
                    f.write(f"{i+1}\n")
                    f.write(f"{format_srt_timestamp(seg['start'])} --> {format_srt_timestamp(seg['end'])}\n")
                    f.write(f"{seg['text'].strip()}\n\n")
            logger.info(f"SRT file saved to: {srt_path}")
            
            # Also save plain text transcript
            txt_path = os.path.join("data/transcriptions", f"{basename}.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(transcript_text)
            logger.info(f"Transcript saved to: {txt_path}")
        
        # Update video status
        video.status = "transcribed"
        db.commit()
        
        # Create summarization job
        create_summarization_job(transcript.id, db)
        
        # Mark job as completed
        processing_time = time.time() - start_time
        mark_job_completed(job, processing_time, db)
        
        logger.info(f"Transcription completed for video {video.filename} in {processing_time:.2f} seconds")
        return True
        
    except Exception as e:
        logger.error(f"Error processing transcription job {job.id}: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        
        # Mark job as failed
        error_details = {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        mark_job_failed(job, error_details, db)
        
        # Update video status if it exists
        if 'video' in locals():
            video.status = "error"
            db.commit()
        
        return False

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
            # Get database session
            with get_db() as db:
                # Get next job
                job = get_next_transcription_job(db)
                
                if job:
                    logger.info(f"Processing transcription job {job.id} for video {job.video_id}")
                    process_transcription_job(job, db)
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
