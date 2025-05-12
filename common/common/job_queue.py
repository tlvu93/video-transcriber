import logging
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Dict, Any

from common.common.models import TranscriptionJob, SummarizationJob

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('job_queue')

def get_next_transcription_job(db: Session) -> Optional[TranscriptionJob]:
    """
    Get the next pending transcription job from the queue.
    
    Args:
        db: Database session
        
    Returns:
        The next pending transcription job, or None if no jobs are pending
    """
    job = db.query(TranscriptionJob)\
            .filter(TranscriptionJob.status == "pending")\
            .order_by(TranscriptionJob.created_at)\
            .first()
    
    if job:
        logger.info(f"Found pending transcription job: {job.id}")
    else:
        logger.debug("No pending transcription jobs found")
    
    return job

def get_next_summarization_job(db: Session) -> Optional[SummarizationJob]:
    """
    Get the next pending summarization job from the queue.
    
    Args:
        db: Database session
        
    Returns:
        The next pending summarization job, or None if no jobs are pending
    """
    job = db.query(SummarizationJob)\
            .filter(SummarizationJob.status == "pending")\
            .order_by(SummarizationJob.created_at)\
            .first()
    
    if job:
        logger.info(f"Found pending summarization job: {job.id}")
    else:
        logger.debug("No pending summarization jobs found")
    
    return job

def mark_job_started(job, db: Session) -> None:
    """
    Mark a job as started.
    
    Args:
        job: The job to mark as started
        db: Database session
    """
    job.status = "processing"
    job.started_at = datetime.utcnow()
    db.commit()
    logger.info(f"Job {job.id} marked as started")

def mark_job_completed(job, processing_time: float, db: Session) -> None:
    """
    Mark a job as completed.
    
    Args:
        job: The job to mark as completed
        processing_time: The time taken to process the job in seconds
        db: Database session
    """
    job.status = "completed"
    job.completed_at = datetime.utcnow()
    job.processing_time_seconds = processing_time
    db.commit()
    logger.info(f"Job {job.id} marked as completed in {processing_time:.2f} seconds")

def mark_job_failed(job, error_details: Dict[str, Any], db: Session) -> None:
    """
    Mark a job as failed.
    
    Args:
        job: The job to mark as failed
        error_details: Details of the error that caused the job to fail
        db: Database session
    """
    job.status = "failed"
    job.completed_at = datetime.utcnow()
    job.error_details = error_details
    db.commit()
    logger.info(f"Job {job.id} marked as failed: {error_details}")

def create_transcription_job(video_id, db: Session) -> TranscriptionJob:
    """
    Create a new transcription job.
    
    Args:
        video_id: ID of the video to transcribe
        db: Database session
        
    Returns:
        The created transcription job
    """
    job = TranscriptionJob(
        video_id=video_id,
        status="pending"
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info(f"Created transcription job {job.id} for video {video_id}")
    return job

def create_summarization_job(transcript_id, db: Session) -> SummarizationJob:
    """
    Create a new summarization job.
    
    Args:
        transcript_id: ID of the transcript to summarize
        db: Database session
        
    Returns:
        The created summarization job
    """
    job = SummarizationJob(
        transcript_id=transcript_id,
        status="pending"
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info(f"Created summarization job {job.id} for transcript {transcript_id}")
    return job
