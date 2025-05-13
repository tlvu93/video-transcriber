import os
import logging
import shutil
import hashlib
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, BackgroundTasks, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from api.database import get_db
from api.models import Video, Transcript, Summary
from api.job_queue import create_transcription_job
from api.config import VIDEO_DIR, TRANSCRIPT_DIR, SUMMARY_DIR

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
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
os.makedirs(SUMMARY_DIR, exist_ok=True)

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
    create_transcription_job(video.id, db)
    
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
    file_path = os.path.join(VIDEO_DIR, video_data.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Video file not found: {video_data.filename}")
    
    # Check if a video with the same filename exists
    existing_video = db.query(Video).filter(Video.filename == video_data.filename).first()
    
    if existing_video:
        logger.info(f"Video {video_data.filename} already exists in the database, updating status")
        existing_video.status = "pending"
        db.commit()
        db.refresh(existing_video)
        return existing_video
    
    # Check if a video with the same file_hash exists
    if video_data.file_hash:
        existing_video_by_hash = db.query(Video).filter(Video.file_hash == video_data.file_hash).first()
        
        if existing_video_by_hash:
            logger.info(f"Video with hash {video_data.file_hash} already exists in the database as {existing_video_by_hash.filename}")
            return existing_video_by_hash
    
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
    
    return video

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
        return existing_video
    
    # Check if a video with the same file_hash exists
    if video_check.file_hash:
        existing_video_by_hash = db.query(Video).filter(Video.file_hash == video_check.file_hash).first()
        
        if existing_video_by_hash:
            logger.info(f"Video with hash {video_check.file_hash} found in the database as {existing_video_by_hash.filename}")
            return existing_video_by_hash
    
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

@app.get("/videos/{video_id}/download")
def download_video(video_id: str, db: Session = Depends(get_db)):
    """
    Download a video by ID.
    
    Args:
        video_id: The ID of the video
        db: Database session
        
    Returns:
        The video file
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    file_path = os.path.join(VIDEO_DIR, video.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    
    return FileResponse(file_path, filename=video.filename)

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
