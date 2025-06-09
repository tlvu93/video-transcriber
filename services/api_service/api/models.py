import uuid
from datetime import datetime

from api.database import Base
from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import relationship


def generate_uuid():
    """Generate a UUID for use as a primary key."""
    return str(uuid.uuid4())


class Video(Base):
    """Video model."""

    __tablename__ = "videos"

    id = Column(String, primary_key=True, default=generate_uuid)
    filename = Column(String, nullable=False)
    file_hash = Column(String, nullable=True)  # Added file_hash field
    status = Column(String, default="pending")  # pending, transcribed, error
    created_at = Column(DateTime, default=datetime.utcnow)
    video_metadata = Column(JSON, default=dict)

    transcripts = relationship("Transcript", back_populates="video")
    transcription_jobs = relationship("TranscriptionJob", back_populates="video")


class Transcript(Base):
    """Transcript model."""

    __tablename__ = "transcripts"

    id = Column(String, primary_key=True, default=generate_uuid)
    video_id = Column(String, ForeignKey("videos.id"), nullable=True)
    source_type = Column(String, default="video")  # video, manual
    content = Column(Text, nullable=False)
    format = Column(String, default="txt")  # txt, srt
    status = Column(String, default="pending")  # pending, completed, summarized, error
    created_at = Column(DateTime, default=datetime.utcnow)
    segments = Column(JSON, nullable=True)  # Store timestamp segments as JSON

    video = relationship("Video", back_populates="transcripts")
    summaries = relationship("Summary", back_populates="transcript")
    summarization_jobs = relationship("SummarizationJob", back_populates="transcript")
    translations = relationship("TranslatedTranscript", back_populates="transcript")
    translation_jobs = relationship("TranslationJob", back_populates="transcript")


class Summary(Base):
    """Summary model."""

    __tablename__ = "summaries"

    id = Column(String, primary_key=True, default=generate_uuid)
    transcript_id = Column(String, ForeignKey("transcripts.id"), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String, default="pending")  # pending, completed, error
    created_at = Column(DateTime, default=datetime.utcnow)

    transcript = relationship("Transcript", back_populates="summaries")


class TranscriptionJob(Base):
    """Transcription job model."""

    __tablename__ = "transcription_jobs"

    id = Column(String, primary_key=True, default=generate_uuid)
    video_id = Column(String, ForeignKey("videos.id"), nullable=False)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)
    error_details = Column(JSON, nullable=True)

    video = relationship("Video", back_populates="transcription_jobs")


class SummarizationJob(Base):
    """Summarization job model."""

    __tablename__ = "summarization_jobs"

    id = Column(String, primary_key=True, default=generate_uuid)
    transcript_id = Column(String, ForeignKey("transcripts.id"), nullable=False)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)
    error_details = Column(JSON, nullable=True)

    transcript = relationship("Transcript", back_populates="summarization_jobs")


class TranslatedTranscript(Base):
    """Translated transcript model."""

    __tablename__ = "translated_transcripts"

    id = Column(String, primary_key=True, default=generate_uuid)
    transcript_id = Column(String, ForeignKey("transcripts.id"), nullable=False)
    language = Column(String, nullable=False)  # Target language code (e.g., "de", "en")
    content = Column(Text, nullable=False)
    segments = Column(JSON, nullable=True)  # Store translated segments as JSON
    status = Column(String, default="completed")  # completed, error
    created_at = Column(DateTime, default=datetime.utcnow)

    transcript = relationship("Transcript", back_populates="translations")


class TranslationJob(Base):
    """Translation job model."""

    __tablename__ = "translation_jobs"

    id = Column(String, primary_key=True, default=generate_uuid)
    transcript_id = Column(String, ForeignKey("transcripts.id"), nullable=False)
    source_language = Column(String, nullable=True)  # If null, auto-detect
    target_language = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)
    error_details = Column(JSON, nullable=True)

    transcript = relationship("Transcript", back_populates="translation_jobs")
