import os
import logging
import json
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from common.common.config import DATABASE_URL, DB_PATH

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('database')

# Create database directory if it doesn't exist
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_db():
    """Initialize the database."""
    from common.common.models import Video, Transcript, Summary, TranscriptionJob, SummarizationJob
    
    logger.info(f"Creating database tables at {DB_PATH}")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

@contextmanager
def get_db():
    """Get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def migrate_from_json_to_db():
    """Migrate data from JSON files to the database."""
    from common.common.models import Video, Transcript, Summary
    
    # Check if migration is needed
    with get_db() as db:
        # If there are already videos in the database, skip migration
        if db.query(Video).count() > 0:
            logger.info("Database already contains data, skipping migration")
            return
    
    # Paths to JSON files
    videos_json = os.path.join(os.path.dirname(DB_PATH), "videos.json")
    transcripts_json = os.path.join(os.path.dirname(DB_PATH), "transcripts.json")
    summaries_json = os.path.join(os.path.dirname(DB_PATH), "summaries.json")
    
    # Check if JSON files exist
    if not (os.path.exists(videos_json) or os.path.exists(transcripts_json) or os.path.exists(summaries_json)):
        logger.info("No JSON files found for migration")
        return
    
    logger.info("Starting migration from JSON to database")
    
    # Migrate videos
    if os.path.exists(videos_json):
        try:
            with open(videos_json, "r") as f:
                videos_data = json.load(f)
            
            with get_db() as db:
                for video_data in videos_data:
                    video = Video(
                        id=video_data.get("id"),
                        filename=video_data.get("filename"),
                        status=video_data.get("status", "pending"),
                        created_at=video_data.get("created_at"),
                        metadata=video_data.get("metadata", {})
                    )
                    db.add(video)
                db.commit()
            
            logger.info(f"Migrated {len(videos_data)} videos from JSON to database")
        except Exception as e:
            logger.error(f"Error migrating videos: {str(e)}")
    
    # Migrate transcripts
    if os.path.exists(transcripts_json):
        try:
            with open(transcripts_json, "r") as f:
                transcripts_data = json.load(f)
            
            with get_db() as db:
                for transcript_data in transcripts_data:
                    transcript = Transcript(
                        id=transcript_data.get("id"),
                        video_id=transcript_data.get("video_id"),
                        source_type=transcript_data.get("source_type", "video"),
                        content=transcript_data.get("content"),
                        format=transcript_data.get("format", "txt"),
                        status=transcript_data.get("status", "completed"),
                        created_at=transcript_data.get("created_at")
                    )
                    db.add(transcript)
                db.commit()
            
            logger.info(f"Migrated {len(transcripts_data)} transcripts from JSON to database")
        except Exception as e:
            logger.error(f"Error migrating transcripts: {str(e)}")
    
    # Migrate summaries
    if os.path.exists(summaries_json):
        try:
            with open(summaries_json, "r") as f:
                summaries_data = json.load(f)
            
            with get_db() as db:
                for summary_data in summaries_data:
                    summary = Summary(
                        id=summary_data.get("id"),
                        transcript_id=summary_data.get("transcript_id"),
                        content=summary_data.get("content"),
                        status=summary_data.get("status", "completed"),
                        created_at=summary_data.get("created_at")
                    )
                    db.add(summary)
                db.commit()
            
            logger.info(f"Migrated {len(summaries_data)} summaries from JSON to database")
        except Exception as e:
            logger.error(f"Error migrating summaries: {str(e)}")
    
    logger.info("Migration from JSON to database completed")
