import os
import logging
import uuid
import shutil
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Query, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from .database import get_db_session, init_db, migrate_from_json_to_db
from .models import Video, Transcript, Summary, TranscriptionJob, SummarizationJob
from .schemas import (
    VideoResponse, VideoDetailResponse, TranscriptResponse, SummaryResponse,
    TranscriptionJobResponse, SummarizationJobResponse, TranscriptCreate,
    AnalyticsOverview, TranscriptionStats, SummarizationStats, AnalyticsTrends
)
from .job_queue import create_transcription_job, create_summarization_job
from .utils import get_file_hash, get_video_metadata

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('api')

# Create FastAPI app
app = FastAPI(
    title="Video Transcriber API",
    description="API for video transcription and summarization",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure directories exist
os.makedirs("data/videos", exist_ok=True)
os.makedirs("data/transcriptions", exist_ok=True)
os.makedirs("data/summaries", exist_ok=True)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    logger.info("Initializing database...")
    init_db()
    
    # Migrate data from JSON to database
    logger.info("Migrating data from JSON to database...")
    migrate_from_json_to_db()

# Video endpoints
@app.post("/api/videos", response_model=VideoResponse)
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session)
):
    """Upload a new video file."""
    try:
        # Save uploaded file
        file_location = os.path.join("data/videos", file.filename)
        with open(file_location, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        # Get file hash and metadata
        file_hash = get_file_hash(file_location)
        if not file_hash:
            raise HTTPException(status_code=500, detail="Failed to calculate file hash")
        
        # Check if video already exists
        existing_video = db.query(Video).filter(Video.file_hash == file_hash).first()
        if existing_video:
            return existing_video
        
        # Get video metadata
        metadata = get_video_metadata(file_location)
        
        # Extract additional metadata
        duration_seconds = None
        resolution_width = None
        resolution_height = None
        file_type = os.path.splitext(file.filename)[1].lstrip('.')
        
        if "format" in metadata and "duration" in metadata["format"]:
            duration_seconds = float(metadata["format"]["duration"])
        
        if "streams" in metadata and len(metadata["streams"]) > 0:
            if "width" in metadata["streams"][0]:
                resolution_width = metadata["streams"][0]["width"]
            if "height" in metadata["streams"][0]:
                resolution_height = metadata["streams"][0]["height"]
        
        # Create video record
        video = Video(
            filename=file.filename,
            file_hash=file_hash,
            status="pending",
            metadata=metadata,
            duration_seconds=duration_seconds,
            file_type=file_type,
            resolution_width=resolution_width,
            resolution_height=resolution_height
        )
        db.add(video)
        db.commit()
        db.refresh(video)
        
        # Create transcription job
        create_transcription_job(video.id, db)
        
        return video
    
    except Exception as e:
        logger.error(f"Error uploading video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/videos", response_model=List[VideoResponse])
def get_videos(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_db_session)
):
    """Get a list of videos."""
    query = db.query(Video)
    
    if status:
        query = query.filter(Video.status == status)
    
    videos = query.order_by(Video.created_at.desc()).offset(skip).limit(limit).all()
    return videos

@app.get("/api/videos/{video_id}", response_model=VideoDetailResponse)
def get_video(
    video_id: uuid.UUID,
    db: Session = Depends(get_db_session)
):
    """Get details of a specific video."""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

@app.delete("/api/videos/{video_id}")
def delete_video(
    video_id: uuid.UUID,
    db: Session = Depends(get_db_session)
):
    """Delete a video and its associated data."""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Delete file from disk
    file_path = os.path.join("data/videos", video.filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # Delete associated transcripts and summaries
    transcripts = db.query(Transcript).filter(Transcript.video_id == video_id).all()
    for transcript in transcripts:
        # Delete associated summaries
        db.query(Summary).filter(Summary.transcript_id == transcript.id).delete()
        
        # Delete associated summarization jobs
        db.query(SummarizationJob).filter(SummarizationJob.transcript_id == transcript.id).delete()
    
    # Delete transcripts
    db.query(Transcript).filter(Transcript.video_id == video_id).delete()
    
    # Delete transcription jobs
    db.query(TranscriptionJob).filter(TranscriptionJob.video_id == video_id).delete()
    
    # Delete video
    db.delete(video)
    db.commit()
    
    return {"message": "Video deleted successfully"}

@app.put("/api/videos/{video_id}/reprocess")
def reprocess_video(
    video_id: uuid.UUID,
    db: Session = Depends(get_db_session)
):
    """Reprocess a video (create new transcription job)."""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Update video status
    video.status = "pending"
    db.commit()
    
    # Create new transcription job
    job = create_transcription_job(video.id, db)
    
    return {"message": "Video reprocessing started", "job_id": job.id}

# Transcript endpoints
@app.get("/api/transcripts", response_model=List[TranscriptResponse])
def get_transcripts(
    skip: int = 0,
    limit: int = 100,
    source_type: Optional[str] = None,
    db: Session = Depends(get_db_session)
):
    """Get a list of transcripts."""
    query = db.query(Transcript)
    
    if source_type:
        query = query.filter(Transcript.source_type == source_type)
    
    transcripts = query.order_by(Transcript.created_at.desc()).offset(skip).limit(limit).all()
    return transcripts

@app.get("/api/transcripts/{transcript_id}", response_model=TranscriptResponse)
def get_transcript(
    transcript_id: uuid.UUID,
    db: Session = Depends(get_db_session)
):
    """Get details of a specific transcript."""
    transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return transcript

@app.post("/api/transcripts", response_model=TranscriptResponse)
def create_transcript(
    transcript: TranscriptCreate,
    db: Session = Depends(get_db_session)
):
    """Create a new manual transcript."""
    # Create transcript record
    db_transcript = Transcript(
        video_id=transcript.video_id,
        source_type=transcript.source_type,
        content=transcript.content,
        format=transcript.format,
        status="completed"
    )
    db.add(db_transcript)
    db.commit()
    db.refresh(db_transcript)
    
    # Create summarization job
    create_summarization_job(db_transcript.id, db)
    
    return db_transcript

@app.put("/api/transcripts/{transcript_id}/summarize")
def summarize_transcript(
    transcript_id: uuid.UUID,
    db: Session = Depends(get_db_session)
):
    """Create a summarization job for a transcript."""
    transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    
    # Create summarization job
    job = create_summarization_job(transcript.id, db)
    
    return {"message": "Summarization started", "job_id": job.id}

# Summary endpoints
@app.get("/api/summaries", response_model=List[SummaryResponse])
def get_summaries(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db_session)
):
    """Get a list of summaries."""
    summaries = db.query(Summary).order_by(Summary.created_at.desc()).offset(skip).limit(limit).all()
    return summaries

@app.get("/api/summaries/{summary_id}", response_model=SummaryResponse)
def get_summary(
    summary_id: uuid.UUID,
    db: Session = Depends(get_db_session)
):
    """Get details of a specific summary."""
    summary = db.query(Summary).filter(Summary.id == summary_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    return summary

# Job endpoints
@app.get("/api/jobs/transcription", response_model=List[TranscriptionJobResponse])
def get_transcription_jobs(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_db_session)
):
    """Get a list of transcription jobs."""
    query = db.query(TranscriptionJob)
    
    if status:
        query = query.filter(TranscriptionJob.status == status)
    
    jobs = query.order_by(TranscriptionJob.created_at.desc()).offset(skip).limit(limit).all()
    return jobs

@app.get("/api/jobs/summarization", response_model=List[SummarizationJobResponse])
def get_summarization_jobs(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_db_session)
):
    """Get a list of summarization jobs."""
    query = db.query(SummarizationJob)
    
    if status:
        query = query.filter(SummarizationJob.status == status)
    
    jobs = query.order_by(SummarizationJob.created_at.desc()).offset(skip).limit(limit).all()
    return jobs

# Analytics endpoints
@app.get("/api/analytics/overview", response_model=AnalyticsOverview)
def get_analytics_overview(
    db: Session = Depends(get_db_session)
):
    """Get overview analytics."""
    # Count videos
    total_videos = db.query(Video).count()
    successful_videos = db.query(Video).filter(Video.status == "transcribed").count()
    failed_videos = db.query(Video).filter(Video.status == "error").count()
    
    # Calculate success rate
    success_rate = successful_videos / total_videos if total_videos > 0 else 0
    
    # Calculate average processing times
    transcription_jobs = db.query(TranscriptionJob).filter(TranscriptionJob.processing_time_seconds != None).all()
    summarization_jobs = db.query(SummarizationJob).filter(SummarizationJob.processing_time_seconds != None).all()
    
    avg_transcription_time = sum(job.processing_time_seconds for job in transcription_jobs) / len(transcription_jobs) if transcription_jobs else 0
    avg_summarization_time = sum(job.processing_time_seconds for job in summarization_jobs) / len(summarization_jobs) if summarization_jobs else 0
    avg_total_time = avg_transcription_time + avg_summarization_time
    
    return {
        "total_videos": total_videos,
        "successful_videos": successful_videos,
        "failed_videos": failed_videos,
        "success_rate": success_rate,
        "avg_transcription_time": avg_transcription_time,
        "avg_summarization_time": avg_summarization_time,
        "avg_total_time": avg_total_time
    }

@app.get("/api/analytics/transcription", response_model=TranscriptionStats)
def get_transcription_stats(
    db: Session = Depends(get_db_session)
):
    """Get transcription analytics."""
    # Count transcriptions
    total_transcriptions = db.query(TranscriptionJob).count()
    successful_transcriptions = db.query(TranscriptionJob).filter(TranscriptionJob.status == "completed").count()
    failed_transcriptions = db.query(TranscriptionJob).filter(TranscriptionJob.status == "failed").count()
    
    # Calculate success rate
    success_rate = successful_transcriptions / total_transcriptions if total_transcriptions > 0 else 0
    
    # Calculate average processing time
    transcription_jobs = db.query(TranscriptionJob).filter(TranscriptionJob.processing_time_seconds != None).all()
    avg_processing_time = sum(job.processing_time_seconds for job in transcription_jobs) / len(transcription_jobs) if transcription_jobs else 0
    
    # Calculate processing time by duration
    processing_time_by_duration = {}
    
    # Get completed jobs with videos
    completed_jobs = db.query(TranscriptionJob, Video)\
        .join(Video, TranscriptionJob.video_id == Video.id)\
        .filter(TranscriptionJob.status == "completed")\
        .filter(TranscriptionJob.processing_time_seconds != None)\
        .filter(Video.duration_seconds != None)\
        .all()
    
    # Group by duration ranges
    duration_ranges = {
        "0-60s": (0, 60),
        "60-300s": (60, 300),
        "300-600s": (300, 600),
        "600-1800s": (600, 1800),
        "1800s+": (1800, float('inf'))
    }
    
    for range_name, (min_duration, max_duration) in duration_ranges.items():
        jobs_in_range = [job for job, video in completed_jobs 
                         if min_duration <= video.duration_seconds < max_duration]
        
        if jobs_in_range:
            avg_time = sum(job.processing_time_seconds for job in jobs_in_range) / len(jobs_in_range)
            processing_time_by_duration[range_name] = avg_time
        else:
            processing_time_by_duration[range_name] = 0
    
    return {
        "total_transcriptions": total_transcriptions,
        "successful_transcriptions": successful_transcriptions,
        "failed_transcriptions": failed_transcriptions,
        "success_rate": success_rate,
        "avg_processing_time": avg_processing_time,
        "processing_time_by_duration": processing_time_by_duration
    }

@app.get("/api/analytics/summarization", response_model=SummarizationStats)
def get_summarization_stats(
    db: Session = Depends(get_db_session)
):
    """Get summarization analytics."""
    # Count summarizations
    total_summarizations = db.query(SummarizationJob).count()
    successful_summarizations = db.query(SummarizationJob).filter(SummarizationJob.status == "completed").count()
    failed_summarizations = db.query(SummarizationJob).filter(SummarizationJob.status == "failed").count()
    
    # Calculate success rate
    success_rate = successful_summarizations / total_summarizations if total_summarizations > 0 else 0
    
    # Calculate average processing time
    summarization_jobs = db.query(SummarizationJob).filter(SummarizationJob.processing_time_seconds != None).all()
    avg_processing_time = sum(job.processing_time_seconds for job in summarization_jobs) / len(summarization_jobs) if summarization_jobs else 0
    
    return {
        "total_summarizations": total_summarizations,
        "successful_summarizations": successful_summarizations,
        "failed_summarizations": failed_summarizations,
        "success_rate": success_rate,
        "avg_processing_time": avg_processing_time
    }

@app.get("/api/analytics/trends", response_model=AnalyticsTrends)
def get_analytics_trends(
    days: int = 7,
    db: Session = Depends(get_db_session)
):
    """Get processing trends over time."""
    trends = []
    
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Generate data for each day
    current_date = start_date
    while current_date <= end_date:
        next_date = current_date + timedelta(days=1)
        
        # Count transcriptions for this day
        transcription_count = db.query(TranscriptionJob)\
            .filter(TranscriptionJob.created_at >= current_date)\
            .filter(TranscriptionJob.created_at < next_date)\
            .count()
        
        # Count summarizations for this day
        summarization_count = db.query(SummarizationJob)\
            .filter(SummarizationJob.created_at >= current_date)\
            .filter(SummarizationJob.created_at < next_date)\
            .count()
        
        # Calculate average transcription time for this day
        transcription_jobs = db.query(TranscriptionJob)\
            .filter(TranscriptionJob.created_at >= current_date)\
            .filter(TranscriptionJob.created_at < next_date)\
            .filter(TranscriptionJob.processing_time_seconds != None)\
            .all()
        
        avg_transcription_time = sum(job.processing_time_seconds for job in transcription_jobs) / len(transcription_jobs) if transcription_jobs else 0
        
        # Calculate average summarization time for this day
        summarization_jobs = db.query(SummarizationJob)\
            .filter(SummarizationJob.created_at >= current_date)\
            .filter(SummarizationJob.created_at < next_date)\
            .filter(SummarizationJob.processing_time_seconds != None)\
            .all()
        
        avg_summarization_time = sum(job.processing_time_seconds for job in summarization_jobs) / len(summarization_jobs) if summarization_jobs else 0
        
        # Add to trends
        trends.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "transcription_count": transcription_count,
            "summarization_count": summarization_count,
            "avg_transcription_time": avg_transcription_time,
            "avg_summarization_time": avg_summarization_time
        })
        
        # Move to next day
        current_date = next_date
    
    return {"trends": trends}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
