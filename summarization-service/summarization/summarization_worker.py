import time
import logging
import os
import traceback
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

import sys
from pathlib import Path

# Add the project root directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from common.common.database import get_db
from common.common.models import Transcript, Summary, SummarizationJob, Video
from common.common.job_queue import get_next_summarization_job, mark_job_started, mark_job_completed, mark_job_failed
from summarization.summarizer import create_summary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('summarization_worker')

def process_summarization_job(job: SummarizationJob, db: Session) -> bool:
    """
    Process a summarization job.
    
    Args:
        job: The summarization job to process
        db: Database session
        
    Returns:
        True if the job was processed successfully, False otherwise
    """
    start_time = time.time()
    
    try:
        # Mark job as started
        mark_job_started(job, db)
        
        # Get transcript
        transcript = db.query(Transcript).filter(Transcript.id == job.transcript_id).first()
        if not transcript:
            raise ValueError(f"Transcript {job.transcript_id} not found")
        
        # Get video filename (if available) for logging
        video_filename = None
        if transcript.video_id:
            video = db.query(Video).filter(Video.id == transcript.video_id).first()
            if video:
                video_filename = video.filename
        
        # Generate summary
        logger.info(f"Generating summary for transcript {job.transcript_id}")
        
        # If transcript is from a video, pass the video path for compatibility with existing code
        video_path = None
        if video_filename:
            video_path = os.path.join("data/videos", video_filename)
        
        summary_text = create_summary(transcript.content, video_path or "manual_transcript")
        
        # Create summary
        summary = Summary(
            transcript_id=transcript.id,
            content=summary_text,
            status="completed"
        )
        db.add(summary)
        db.commit()
        
        # Save summary to file system for backward compatibility
        if video_filename:
            os.makedirs("data/summaries", exist_ok=True)
            basename = os.path.splitext(video_filename)[0]
            summary_path = os.path.join("data/summaries", f"{basename}_summary.txt")
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(summary_text)
            logger.info(f"Summary saved to: {summary_path}")
        
        # Update transcript status
        transcript.status = "summarized"
        db.commit()
        
        # Mark job as completed
        processing_time = time.time() - start_time
        mark_job_completed(job, processing_time, db)
        
        logger.info(f"Summarization completed for transcript {job.transcript_id} in {processing_time:.2f} seconds")
        return True
        
    except Exception as e:
        logger.error(f"Error processing summarization job {job.id}: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        
        # Mark job as failed
        error_details = {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        mark_job_failed(job, error_details, db)
        
        # Update transcript status if it exists
        if 'transcript' in locals():
            transcript.status = "error"
            db.commit()
        
        return False

def start_worker(poll_interval: int = 5):
    """
    Start the summarization worker.
    
    Args:
        poll_interval: Time in seconds to wait between polling for new jobs
    """
    logger.info("Starting summarization worker")
    
    while True:
        try:
            # Get database session
            with get_db() as db:
                # Get next job
                job = get_next_summarization_job(db)
                
                if job:
                    logger.info(f"Processing summarization job {job.id} for transcript {job.transcript_id}")
                    process_summarization_job(job, db)
                else:
                    logger.debug("No pending summarization jobs")
            
            # Wait before checking for new jobs
            time.sleep(poll_interval)
            
        except Exception as e:
            logger.error(f"Error in summarization worker: {str(e)}")
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            time.sleep(poll_interval)

if __name__ == "__main__":
    start_worker()
