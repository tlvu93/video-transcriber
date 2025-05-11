import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

from .models import Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('database')

# Get database URL from environment variable or use default
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://videotranscriber:videotranscriber@localhost/videotranscriber")

# Create engine
engine = create_engine(DATABASE_URL)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initialize the database by creating all tables."""
    try:
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")
        raise

def get_db_session():
    """Get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_db():
    """Context manager for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def migrate_from_json_to_db():
    """Migrate data from the JSON file to the database."""
    from .config import DB_PATH
    import json
    import os
    from .models import Video, Transcript, Summary, TranscriptionJob, SummarizationJob
    
    if not os.path.exists(DB_PATH):
        logger.warning(f"JSON database file not found: {DB_PATH}")
        return
    
    try:
        logger.info(f"Migrating data from JSON file: {DB_PATH}")
        
        # Load JSON data
        with open(DB_PATH, "r") as f:
            json_db = json.load(f)
        
        logger.info(f"Loaded {len(json_db)} entries from JSON file")
        
        # Create database session
        with get_db() as db:
            # Process each entry
            for file_hash, data in json_db.items():
                # Check if video already exists
                existing_video = db.query(Video).filter(Video.file_hash == file_hash).first()
                if existing_video:
                    logger.info(f"Video already exists in database: {data['filename']}")
                    continue
                
                # Create video record
                video = Video(
                    file_hash=file_hash,
                    filename=data["filename"],
                    status="completed",
                    metadata=data.get("metadata", {}),
                )
                
                # Extract additional metadata if available
                if "metadata" in data and "format" in data["metadata"] and "duration" in data["metadata"]["format"]:
                    video.duration_seconds = float(data["metadata"]["format"]["duration"])
                
                if "metadata" in data and "streams" in data["metadata"] and len(data["metadata"]["streams"]) > 0:
                    if "width" in data["metadata"]["streams"][0]:
                        video.resolution_width = data["metadata"]["streams"][0]["width"]
                    if "height" in data["metadata"]["streams"][0]:
                        video.resolution_height = data["metadata"]["streams"][0]["height"]
                
                # Extract file type
                video.file_type = os.path.splitext(data["filename"])[1].lstrip('.')
                
                db.add(video)
                db.flush()  # Flush to get the video ID
                
                # Create transcript record if available
                transcript_path = os.path.join("data/transcriptions", f"{os.path.splitext(data['filename'])[0]}.txt")
                if os.path.exists(transcript_path):
                    with open(transcript_path, "r", encoding="utf-8") as f:
                        transcript_content = f.read()
                    
                    transcript = Transcript(
                        video_id=video.id,
                        source_type="video",
                        content=transcript_content,
                        format="txt",
                        status="completed"
                    )
                    db.add(transcript)
                    db.flush()  # Flush to get the transcript ID
                    
                    # Create transcription job record
                    transcription_job = TranscriptionJob(
                        video_id=video.id,
                        status="completed",
                        processing_time_seconds=None  # We don't have this information
                    )
                    db.add(transcription_job)
                    
                    # Create summary record if available
                    summary_path = os.path.join("data/summaries", f"{os.path.splitext(data['filename'])[0]}_summary.txt")
                    if os.path.exists(summary_path):
                        with open(summary_path, "r", encoding="utf-8") as f:
                            summary_content = f.read()
                        
                        summary = Summary(
                            transcript_id=transcript.id,
                            content=summary_content,
                            status="completed"
                        )
                        db.add(summary)
                        
                        # Create summarization job record
                        summarization_job = SummarizationJob(
                            transcript_id=transcript.id,
                            status="completed",
                            processing_time_seconds=None  # We don't have this information
                        )
                        db.add(summarization_job)
            
            # Commit all changes
            db.commit()
            logger.info("Data migration completed successfully")
    
    except Exception as e:
        logger.error(f"Error migrating data: {str(e)}")
        raise
