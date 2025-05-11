import uuid
from sqlalchemy import Column, String, Float, Integer, ForeignKey, JSON, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Video(Base):
    __tablename__ = "videos"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String, nullable=False)
    file_hash = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String, default="pending")
    video_metadata = Column(JSONB)  # Renamed from 'metadata' which is a reserved name in SQLAlchemy
    duration_seconds = Column(Float)
    language = Column(String)
    file_type = Column(String)
    resolution_width = Column(Integer)
    resolution_height = Column(Integer)
    
    transcripts = relationship("Transcript", back_populates="video")
    transcription_jobs = relationship("TranscriptionJob", back_populates="video")

class Transcript(Base):
    __tablename__ = "transcripts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id"), nullable=True)
    source_type = Column(String, default="video")  # 'video' or 'manual'
    content = Column(Text)
    format = Column(String, default="txt")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String, default="pending")
    
    video = relationship("Video", back_populates="transcripts")
    summaries = relationship("Summary", back_populates="transcript")
    summarization_jobs = relationship("SummarizationJob", back_populates="transcript")

class Summary(Base):
    __tablename__ = "summaries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transcript_id = Column(UUID(as_uuid=True), ForeignKey("transcripts.id"))
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String, default="pending")
    
    transcript = relationship("Transcript", back_populates="summaries")

class TranscriptionJob(Base):
    __tablename__ = "transcription_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id = Column(UUID(as_uuid=True), ForeignKey("videos.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    error_details = Column(JSONB, nullable=True)
    
    video = relationship("Video", back_populates="transcription_jobs")

class SummarizationJob(Base):
    __tablename__ = "summarization_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transcript_id = Column(UUID(as_uuid=True), ForeignKey("transcripts.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    error_details = Column(JSONB, nullable=True)
    
    transcript = relationship("Transcript", back_populates="summarization_jobs")
