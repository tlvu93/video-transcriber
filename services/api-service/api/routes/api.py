import os
import logging
import shutil
import hashlib
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, BackgroundTasks, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from api.database import get_db
from api.models import Video, Transcript, Summary, TranscriptionJob, SummarizationJob
from api.job_queue import (
    create_transcription_job, create_summarization_job,
    get_next_transcription_job, get_next_summarization_job,
    mark_job_started, mark_job_completed, mark_job_failed
)
from api.config import VIDEO_DIR, VIDEO_DIRS
from common.messaging import (
    RabbitMQClient, 
    publish_video_created_event,
    publish_transcription_created_event,
    publish_summary_created_event,
    publish_job_status_changed_event
)

# Initialize RabbitMQ client
rabbitmq_client = RabbitMQClient()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('api')

# Create FastAPI app
app = FastAPI(title="Video Transcriber API")

# Ensure directories exist
os.makedirs(VIDEO_DIR, exist_ok=True)

# Pydantic models for request/response
class VideoCreate(BaseModel):
    filename: str
    file_hash: Optional[str] = None
    video_metadata: Optional[Dict[str, Any]] = None

class VideoCheck(BaseModel):
    filename: str
    file_hash: Optional[str] = None

class VideoResponse(BaseModel):
    id: str
    filename: str
    status: str
    created_at: Any
    file_hash: Optional[str] = None
    video_metadata: Optional[Dict[str, Any]] = None

class TranscriptionJobCreate(BaseModel):
    video_id: str

class TranscriptionJobResponse(BaseModel):
    id: str
    video_id: str
    status: str
    created_at: Any
    started_at: Optional[Any] = None
    completed_at: Optional[Any] = None
    processing_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None

class TranscriptionJobUpdate(BaseModel):
    status: Optional[str] = None
    processing_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None

class SummarizationJobCreate(BaseModel):
    transcript_id: str

class SummarizationJobResponse(BaseModel):
    id: str
    transcript_id: str
    status: str
    created_at: Any
    started_at: Optional[Any] = None
    completed_at: Optional[Any] = None
    processing_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None

class SummarizationJobUpdate(BaseModel):
    status: Optional[str] = None
    processing_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None

class SummaryCreate(BaseModel):
    transcript_id: str
    content: str
    status: str = "completed"

class SummaryResponse(BaseModel):
    id: str
    transcript_id: str
    content: str
    status: str
    created_at: Any

class TranscriptCreate(BaseModel):
    video_id: str
    source_type: str = "video"
    content: str
    format: str = "txt"
    status: str = "completed"
    segments: Optional[List[Dict[str, Any]]] = None

class TranscriptResponse(BaseModel):
    id: str
    video_id: str
    source_type: str
    content: str
    format: str
    status: str
    created_at: Any
    segments: Optional[List[Dict[str, Any]]] = None

class VideoUpdate(BaseModel):
    status: Optional[str] = None
    video_metadata: Optional[Dict[str, Any]] = None

@app.get("/")
def read_root():
    """Root endpoint."""
    return {"message": "Video Transcriber API"}

@app.post("/videos/")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a video file for transcription.
    
    Args:
        background_tasks: FastAPI background tasks
        file: The video file to upload
        db: Database session
        
    Returns:
        The created video object
    """
    logger.info(f"Received video upload: {file.filename}")
    
    # Save the video file
    file_path = os.path.join(VIDEO_DIR, file.filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Error saving video file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving video file: {str(e)}")
    
    # Create video record
    video = Video(filename=file.filename)
    db.add(video)
    db.commit()
    db.refresh(video)
    
    # Create transcription job
    job = create_transcription_job(video.id, db)
    
    # Publish video created event
    try:
        rabbitmq_client.connect()
        publish_video_created_event(rabbitmq_client, str(video.id), video.filename)
        publish_job_status_changed_event(rabbitmq_client, "transcription", str(job.id), "pending")
    except Exception as e:
        logger.error(f"Error publishing event: {str(e)}")
    
    return {
        "id": video.id,
        "filename": video.filename,
        "status": video.status,
        "created_at": video.created_at
    }

@app.post("/videos/register", response_model=VideoResponse)
async def register_video(
    video_data: VideoCreate,
    db: Session = Depends(get_db)
):
    """
    Register a video file that already exists in the videos directory.
    Used by the watcher service.
    
    Args:
        video_data: The video data
        db: Database session
        
    Returns:
        The created or updated video object
    """
    logger.info(f"Registering video: {video_data.filename}")
    
    # Check if the video file exists
    filename = video_data.filename
    file_path = os.path.join(VIDEO_DIR, filename)
    
    # If file doesn't exist at the expected path, search in all video directories and their subdirectories
    if not os.path.exists(file_path):
        logger.info(f"Video file not found at {file_path}, searching in all video directories...")
        found = False
        
        # Search in all configured video directories
        for video_dir in VIDEO_DIRS:
            # First check directly in the video directory
            test_path = os.path.join(video_dir, filename)
            if os.path.exists(test_path):
                file_path = test_path
                logger.info(f"Found video file at: {file_path}")
                found = True
                break
            
            # Then search in subdirectories
            for root, _, files in os.walk(video_dir):
                if filename in files:
                    file_path = os.path.join(root, filename)
                    logger.info(f"Found video file at: {file_path}")
                    found = True
                    break
            
            if found:
                break
        
        if not found:
            raise HTTPException(status_code=404, detail=f"Video file not found: {filename}")
    
    # Check if a video with the same filename exists
    existing_video = db.query(Video).filter(Video.filename == video_data.filename).first()
    
    if existing_video:
        logger.info(f"Video {video_data.filename} already exists in the database, updating status")
        existing_video.status = "pending"
        db.commit()
        db.refresh(existing_video)
        return {
            "id": str(existing_video.id),
            "filename": existing_video.filename,
            "status": existing_video.status,
            "created_at": existing_video.created_at,
            "file_hash": existing_video.file_hash,
            "video_metadata": existing_video.video_metadata
        }
    
    # Check if a video with the same file_hash exists
    if video_data.file_hash:
        existing_video_by_hash = db.query(Video).filter(Video.file_hash == video_data.file_hash).first()
        
        if existing_video_by_hash:
            logger.info(f"Video with hash {video_data.file_hash} already exists in the database as {existing_video_by_hash.filename}")
            return {
                "id": str(existing_video_by_hash.id),
                "filename": existing_video_by_hash.filename,
                "status": existing_video_by_hash.status,
                "created_at": existing_video_by_hash.created_at,
                "file_hash": existing_video_by_hash.file_hash,
                "video_metadata": existing_video_by_hash.video_metadata
            }
    
    # Create a new video record
    video = Video(
        filename=video_data.filename,
        file_hash=video_data.file_hash,
        status="pending",
        video_metadata=video_data.video_metadata or {"file_hash": video_data.file_hash}
    )
    
    db.add(video)
    db.commit()
    db.refresh(video)
    
    logger.info(f"Added video {video_data.filename} to the database with ID: {video.id}")
    
    return {
        "id": str(video.id),
        "filename": video.filename,
        "status": video.status,
        "created_at": video.created_at,
        "file_hash": video.file_hash,
        "video_metadata": video.video_metadata
    }

@app.post("/videos/check", response_model=Optional[VideoResponse])
async def check_video_exists(
    video_check: VideoCheck,
    db: Session = Depends(get_db)
):
    """
    Check if a video exists in the database by filename or file hash.
    Used by the watcher service.
    
    Args:
        video_check: The video check data
        db: Database session
        
    Returns:
        The video object if found, None otherwise
    """
    logger.info(f"Checking if video exists: {video_check.filename}")
    
    # Check if a video with the same filename exists
    existing_video = db.query(Video).filter(Video.filename == video_check.filename).first()
    
    if existing_video:
        logger.info(f"Video {video_check.filename} found in the database")
        return {
            "id": str(existing_video.id),
            "filename": existing_video.filename,
            "status": existing_video.status,
            "created_at": existing_video.created_at,
            "file_hash": existing_video.file_hash,
            "video_metadata": existing_video.video_metadata
        }
    
    # Check if a video with the same file_hash exists
    if video_check.file_hash:
        existing_video_by_hash = db.query(Video).filter(Video.file_hash == video_check.file_hash).first()
        
        if existing_video_by_hash:
            logger.info(f"Video with hash {video_check.file_hash} found in the database as {existing_video_by_hash.filename}")
            return {
                "id": str(existing_video_by_hash.id),
                "filename": existing_video_by_hash.filename,
                "status": existing_video_by_hash.status,
                "created_at": existing_video_by_hash.created_at,
                "file_hash": existing_video_by_hash.file_hash,
                "video_metadata": existing_video_by_hash.video_metadata
            }
    
    logger.info(f"Video {video_check.filename} not found in the database")
    return None

@app.post("/transcription-jobs/", response_model=TranscriptionJobResponse)
async def create_transcription_job_endpoint(
    job_data: TranscriptionJobCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new transcription job.
    Used by the watcher service.
    
    Args:
        job_data: The job data
        db: Database session
        
    Returns:
        The created transcription job
    """
    logger.info(f"Creating transcription job for video: {job_data.video_id}")
    
    # Check if the video exists
    video = db.query(Video).filter(Video.id == job_data.video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail=f"Video not found: {job_data.video_id}")
    
    # Create a transcription job
    job = create_transcription_job(job_data.video_id, db)
    
    return job

@app.get("/transcription-jobs/next", response_model=Optional[TranscriptionJobResponse])
async def get_next_transcription_job_endpoint(db: Session = Depends(get_db)):
    """
    Get the next pending transcription job.
    Used by the transcription worker.
    
    Args:
        db: Database session
        
    Returns:
        The next pending transcription job, or 404 if no jobs are pending
    """
    job = get_next_transcription_job(db)
    if not job:
        raise HTTPException(status_code=404, detail="No pending transcription jobs")
    return job

@app.get("/transcription-jobs/{job_id}", response_model=TranscriptionJobResponse)
async def get_transcription_job(job_id: str, db: Session = Depends(get_db)):
    """
    Get a transcription job by ID.
    
    Args:
        job_id: The ID of the job
        db: Database session
        
    Returns:
        The transcription job
    """
    job = db.query(TranscriptionJob).filter(TranscriptionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Transcription job not found: {job_id}")
    return job

@app.post("/transcription-jobs/{job_id}/start", response_model=TranscriptionJobResponse)
async def start_transcription_job(job_id: str, db: Session = Depends(get_db)):
    """
    Mark a transcription job as started.
    Used by the transcription worker.
    
    Args:
        job_id: The ID of the job
        db: Database session
        
    Returns:
        The updated transcription job
    """
    job = db.query(TranscriptionJob).filter(TranscriptionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Transcription job not found: {job_id}")
    
    mark_job_started(job, db)
    
    # Publish job status changed event
    try:
        rabbitmq_client.connect()
        publish_job_status_changed_event(rabbitmq_client, "transcription", str(job.id), "processing")
    except Exception as e:
        logger.error(f"Error publishing event: {str(e)}")
    
    return job

@app.post("/transcription-jobs/{job_id}/complete", response_model=TranscriptionJobResponse)
async def complete_transcription_job(
    job_id: str,
    update_data: TranscriptionJobUpdate,
    db: Session = Depends(get_db)
):
    """
    Mark a transcription job as completed.
    Used by the transcription worker.
    
    Args:
        job_id: The ID of the job
        update_data: The update data
        db: Database session
        
    Returns:
        The updated transcription job
    """
    job = db.query(TranscriptionJob).filter(TranscriptionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Transcription job not found: {job_id}")
    
    mark_job_completed(job, update_data.processing_time_seconds, db)
    return job

@app.post("/transcription-jobs/{job_id}/fail", response_model=TranscriptionJobResponse)
async def fail_transcription_job(
    job_id: str,
    update_data: TranscriptionJobUpdate,
    db: Session = Depends(get_db)
):
    """
    Mark a transcription job as failed.
    Used by the transcription worker.
    
    Args:
        job_id: The ID of the job
        update_data: The update data
        db: Database session
        
    Returns:
        The updated transcription job
    """
    job = db.query(TranscriptionJob).filter(TranscriptionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Transcription job not found: {job_id}")
    
    mark_job_failed(job, update_data.error_details, db)
    return job

@app.post("/transcription-jobs/{job_id}/retry", response_model=TranscriptionJobResponse)
async def retry_transcription_job(
    job_id: str,
    db: Session = Depends(get_db)
):
    """
    Retry a failed transcription job by setting its status back to pending.
    
    Args:
        job_id: The ID of the job to retry
        db: Database session
        
    Returns:
        The updated transcription job
    """
    job = db.query(TranscriptionJob).filter(TranscriptionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Transcription job not found: {job_id}")
    
    if job.status != "failed":
        raise HTTPException(status_code=400, detail=f"Job {job_id} is not in failed status, current status: {job.status}")
    
    # Reset job status to pending
    job.status = "pending"
    job.started_at = None
    job.completed_at = None
    job.processing_time_seconds = None
    job.error_details = None
    db.commit()
    db.refresh(job)
    
    logger.info(f"Transcription job {job_id} has been reset to pending status for retry")
    return job

@app.post("/summarization-jobs/", response_model=SummarizationJobResponse)
async def create_summarization_job_endpoint(
    job_data: SummarizationJobCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new summarization job.
    Used by the transcription worker.
    
    Args:
        job_data: The job data
        db: Database session
        
    Returns:
        The created summarization job
    """
    logger.info(f"Creating summarization job for transcript: {job_data.transcript_id}")
    
    # Check if the transcript exists
    transcript = db.query(Transcript).filter(Transcript.id == job_data.transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail=f"Transcript not found: {job_data.transcript_id}")
    
    # Create a summarization job
    job = create_summarization_job(job_data.transcript_id, db)
    
    return job

@app.get("/summarization-jobs/next", response_model=Optional[SummarizationJobResponse])
async def get_next_summarization_job_endpoint(db: Session = Depends(get_db)):
    """
    Get the next pending summarization job.
    Used by the summarization worker.
    
    Args:
        db: Database session
        
    Returns:
        The next pending summarization job, or 404 if no jobs are pending
    """
    job = get_next_summarization_job(db)
    if not job:
        raise HTTPException(status_code=404, detail="No pending summarization jobs")
    return job

@app.get("/summarization-jobs/{job_id}", response_model=SummarizationJobResponse)
async def get_summarization_job(job_id: str, db: Session = Depends(get_db)):
    """
    Get a summarization job by ID.
    
    Args:
        job_id: The ID of the job
        db: Database session
        
    Returns:
        The summarization job
    """
    job = db.query(SummarizationJob).filter(SummarizationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Summarization job not found: {job_id}")
    return job

@app.post("/summarization-jobs/{job_id}/start", response_model=SummarizationJobResponse)
async def start_summarization_job(job_id: str, db: Session = Depends(get_db)):
    """
    Mark a summarization job as started.
    Used by the summarization worker.
    
    Args:
        job_id: The ID of the job
        db: Database session
        
    Returns:
        The updated summarization job
    """
    job = db.query(SummarizationJob).filter(SummarizationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Summarization job not found: {job_id}")
    
    mark_job_started(job, db)
    return job

@app.post("/summarization-jobs/{job_id}/complete", response_model=SummarizationJobResponse)
async def complete_summarization_job(
    job_id: str,
    update_data: SummarizationJobUpdate,
    db: Session = Depends(get_db)
):
    """
    Mark a summarization job as completed.
    Used by the summarization worker.
    
    Args:
        job_id: The ID of the job
        update_data: The update data
        db: Database session
        
    Returns:
        The updated summarization job
    """
    job = db.query(SummarizationJob).filter(SummarizationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Summarization job not found: {job_id}")
    
    mark_job_completed(job, update_data.processing_time_seconds, db)
    return job

@app.post("/summarization-jobs/{job_id}/fail", response_model=SummarizationJobResponse)
async def fail_summarization_job(
    job_id: str,
    update_data: SummarizationJobUpdate,
    db: Session = Depends(get_db)
):
    """
    Mark a summarization job as failed.
    Used by the summarization worker.
    
    Args:
        job_id: The ID of the job
        update_data: The update data
        db: Database session
        
    Returns:
        The updated summarization job
    """
    job = db.query(SummarizationJob).filter(SummarizationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Summarization job not found: {job_id}")
    
    mark_job_failed(job, update_data.error_details, db)
    return job

@app.post("/summaries/", response_model=SummaryResponse)
async def create_summary(
    summary_data: SummaryCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new summary.
    Used by the summarization worker.
    
    Args:
        summary_data: The summary data
        db: Database session
        
    Returns:
        The created summary
    """
    logger.info(f"Creating summary for transcript: {summary_data.transcript_id}")
    
    # Check if the transcript exists
    transcript = db.query(Transcript).filter(Transcript.id == summary_data.transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail=f"Transcript not found: {summary_data.transcript_id}")
    
    # Create a summary
    summary = Summary(
        transcript_id=summary_data.transcript_id,
        content=summary_data.content,
        status=summary_data.status
    )
    db.add(summary)
    db.commit()
    db.refresh(summary)
    
    # Publish summary created event
    try:
        rabbitmq_client.connect()
        publish_summary_created_event(rabbitmq_client, str(summary.id), str(summary.transcript_id))
    except Exception as e:
        logger.error(f"Error publishing event: {str(e)}")
    
    return summary

@app.patch("/transcripts/{transcript_id}", response_model=TranscriptResponse)
async def update_transcript(
    transcript_id: str,
    update_data: dict,
    db: Session = Depends(get_db)
):
    """
    Update a transcript.
    Used by the summarization worker.
    
    Args:
        transcript_id: The ID of the transcript
        update_data: The update data
        db: Database session
        
    Returns:
        The updated transcript
    """
    transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail=f"Transcript not found: {transcript_id}")
    
    if "status" in update_data:
        transcript.status = update_data["status"]
    
    db.commit()
    db.refresh(transcript)
    
    return transcript

@app.post("/transcripts/", response_model=TranscriptResponse)
async def create_transcript(
    transcript_data: TranscriptCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new transcript.
    Used by the transcription worker.
    
    Args:
        transcript_data: The transcript data
        db: Database session
        
    Returns:
        The created transcript
    """
    logger.info(f"Creating transcript for video: {transcript_data.video_id}")
    
    # Check if the video exists
    video = db.query(Video).filter(Video.id == transcript_data.video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail=f"Video not found: {transcript_data.video_id}")
    
    # Create a transcript
    transcript = Transcript(
        video_id=transcript_data.video_id,
        source_type=transcript_data.source_type,
        content=transcript_data.content,
        format=transcript_data.format,
        status=transcript_data.status,
        segments=transcript_data.segments
    )
    db.add(transcript)
    db.commit()
    db.refresh(transcript)
    
    # Publish transcript created event
    try:
        rabbitmq_client.connect()
        publish_transcription_created_event(rabbitmq_client, str(transcript.id), str(transcript.video_id))
    except Exception as e:
        logger.error(f"Error publishing event: {str(e)}")
    
    return transcript

@app.patch("/videos/{video_id}", response_model=VideoResponse)
async def update_video(
    video_id: str,
    update_data: VideoUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a video.
    Used by the transcription worker.
    
    Args:
        video_id: The ID of the video
        update_data: The update data
        db: Database session
        
    Returns:
        The updated video
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")
    
    if update_data.status is not None:
        video.status = update_data.status
    
    if update_data.video_metadata is not None:
        video.video_metadata = update_data.video_metadata
    
    db.commit()
    db.refresh(video)
    
    return {
        "id": str(video.id),
        "filename": video.filename,
        "status": video.status,
        "created_at": video.created_at,
        "file_hash": video.file_hash,
        "video_metadata": video.video_metadata
    }

@app.get("/videos/")
def list_videos(db: Session = Depends(get_db)):
    """
    List all videos.
    
    Args:
        db: Database session
        
    Returns:
        List of videos
    """
    videos = db.query(Video).all()
    return videos

@app.get("/videos/{video_id}")
def get_video(video_id: str, db: Session = Depends(get_db)):
    """
    Get a video by ID.
    
    Args:
        video_id: The ID of the video
        db: Database session
        
    Returns:
        The video object
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

from fastapi import Request, Response
from fastapi.responses import StreamingResponse
import re
import stat

@app.get("/videos/{video_id}/download")
def download_video(video_id: str, request: Request, db: Session = Depends(get_db)):
    """
    Download a video by ID with support for HTTP Range requests.
    
    Args:
        video_id: The ID of the video
        request: The FastAPI request object
        db: Database session
        
    Returns:
        The video file with support for partial content
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Try to find the video file in all video directories
    filename = video.filename
    file_path = os.path.join(VIDEO_DIR, filename)
    
    # If file doesn't exist at the expected path, search in all video directories and their subdirectories
    if not os.path.exists(file_path):
        logger.info(f"Video file not found at {file_path}, searching in all video directories...")
        found = False
        
        # Search in all configured video directories
        for video_dir in VIDEO_DIRS:
            # First check directly in the video directory
            test_path = os.path.join(video_dir, filename)
            if os.path.exists(test_path):
                file_path = test_path
                logger.info(f"Found video file at: {file_path}")
                found = True
                break
            
            # Then search in subdirectories
            for root, _, files in os.walk(video_dir):
                if filename in files:
                    file_path = os.path.join(root, filename)
                    logger.info(f"Found video file at: {file_path}")
                    found = True
                    break
            
            if found:
                break
        
        if not found:
            raise HTTPException(status_code=404, detail=f"Video file not found: {filename}")
    
    # Get file size
    file_size = os.stat(file_path)[stat.ST_SIZE]
    
    # Check if Range header exists
    range_header = request.headers.get("Range", None)
    
    # If no Range header, return the full file
    if range_header is None:
        return FileResponse(file_path, filename=video.filename)
    
    # Parse the Range header
    range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
    if not range_match:
        # If Range header is invalid, return the full file
        return FileResponse(file_path, filename=video.filename)
    
    # Extract start and end bytes
    start_byte = int(range_match.group(1))
    end_byte_str = range_match.group(2)
    end_byte = int(end_byte_str) if end_byte_str else file_size - 1
    
    # Ensure end byte is not beyond file size
    end_byte = min(end_byte, file_size - 1)
    
    # Calculate content length
    content_length = end_byte - start_byte + 1
    
    # Define a generator to stream the file in chunks
    def file_iterator(start, end, chunk_size=8192):
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = f.read(min(chunk_size, remaining))
                if not chunk:
                    break
                yield chunk
                remaining -= len(chunk)
    
    # Create response headers
    headers = {
        "Content-Range": f"bytes {start_byte}-{end_byte}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Disposition": f'attachment; filename="{video.filename}"',
    }
    
    # Determine the media type based on file extension
    import mimetypes
    file_extension = os.path.splitext(video.filename)[1].lower()
    media_type = mimetypes.guess_type(video.filename)[0]
    
    # Default to video/mp4 if we can't determine the media type
    if not media_type:
        if file_extension in ['.mp4', '.m4v']:
            media_type = "video/mp4"
        elif file_extension in ['.mov', '.qt']:
            media_type = "video/quicktime"
        elif file_extension in ['.avi']:
            media_type = "video/x-msvideo"
        elif file_extension in ['.wmv']:
            media_type = "video/x-ms-wmv"
        elif file_extension in ['.webm']:
            media_type = "video/webm"
        else:
            media_type = "video/mp4"  # Default fallback
    
    logger.info(f"Serving video {video.filename} with media type: {media_type}")
    
    # Return a streaming response with the appropriate status code and headers
    return StreamingResponse(
        file_iterator(start_byte, end_byte),
        status_code=206,  # Partial Content
        headers=headers,
        media_type=media_type
    )

@app.get("/transcripts/")
def list_transcripts(video_id: Optional[str] = None, db: Session = Depends(get_db)):
    """
    List all transcripts, optionally filtered by video ID.
    
    Args:
        video_id: Optional video ID to filter by
        db: Database session
        
    Returns:
        List of transcripts
    """
    if video_id:
        transcripts = db.query(Transcript).filter(Transcript.video_id == video_id).all()
    else:
        transcripts = db.query(Transcript).all()
    return transcripts

@app.get("/transcripts/{transcript_id}")
def get_transcript(transcript_id: str, db: Session = Depends(get_db)):
    """
    Get a transcript by ID.
    
    Args:
        transcript_id: The ID of the transcript
        db: Database session
        
    Returns:
        The transcript object
    """
    transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return transcript

@app.get("/summaries/")
def list_summaries(transcript_id: Optional[str] = None, db: Session = Depends(get_db)):
    """
    List all summaries, optionally filtered by transcript ID.
    
    Args:
        transcript_id: Optional transcript ID to filter by
        db: Database session
        
    Returns:
        List of summaries
    """
    if transcript_id:
        summaries = db.query(Summary).filter(Summary.transcript_id == transcript_id).all()
    else:
        summaries = db.query(Summary).all()
    return summaries

@app.get("/summaries/{summary_id}")
def get_summary(summary_id: str, db: Session = Depends(get_db)):
    """
    Get a summary by ID.
    
    Args:
        summary_id: The ID of the summary
        db: Database session
        
    Returns:
        The summary object
    """
    summary = db.query(Summary).filter(Summary.id == summary_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    return summary
