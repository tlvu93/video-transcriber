import uuid
from datetime import datetime

from api.database import Base
from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship


def generate_uuid():
    """Generate a UUID for use as a primary key."""
    return str(uuid.uuid4())


class LeasedJobMixin:
    """Common lease state shared by all queue-backed jobs."""

    worker_id = Column(String, nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)


class Video(Base):
    """Video model."""

    __tablename__ = "videos"
    __table_args__ = (
        Index("ix_videos_file_hash", "file_hash"),
        UniqueConstraint("storage_path", name="uq_videos_storage_path"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    filename = Column(String, nullable=False)
    file_hash = Column(String, nullable=True)
    storage_path = Column(String, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    video_metadata = Column(JSON, default=dict)

    transcripts = relationship("Transcript", back_populates="video")
    transcription_jobs = relationship("TranscriptionJob", back_populates="video")


class Transcript(Base):
    """Transcript model."""

    __tablename__ = "transcripts"
    __table_args__ = (Index("ix_transcripts_video_id", "video_id"),)

    id = Column(String, primary_key=True, default=generate_uuid)
    video_id = Column(String, ForeignKey("videos.id"), nullable=True)
    source_type = Column(String, default="video")
    content = Column(Text, nullable=False)
    format = Column(String, default="txt")
    status = Column(String, default="pending")
    language_code = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    segments = Column(JSON, nullable=True)

    video = relationship("Video", back_populates="transcripts")
    summaries = relationship("Summary", back_populates="transcript")
    summarization_jobs = relationship("SummarizationJob", back_populates="transcript")
    translations = relationship("TranslatedTranscript", back_populates="transcript")
    translation_jobs = relationship("TranslationJob", back_populates="transcript")
    search_segments = relationship(
        "TranscriptSegmentSearch",
        back_populates="transcript",
        cascade="all, delete-orphan",
    )


class Summary(Base):
    """Summary model."""

    __tablename__ = "summaries"

    id = Column(String, primary_key=True, default=generate_uuid)
    transcript_id = Column(String, ForeignKey("transcripts.id"), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String, default="pending")  # pending, completed, error
    created_at = Column(DateTime, default=datetime.utcnow)

    transcript = relationship("Transcript", back_populates="summaries")


class TranscriptionJob(LeasedJobMixin, Base):
    """Transcription job model."""

    __tablename__ = "transcription_jobs"
    __table_args__ = (Index("ix_transcription_jobs_status_created_at", "status", "created_at"),)

    id = Column(String, primary_key=True, default=generate_uuid)
    video_id = Column(String, ForeignKey("videos.id"), nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)
    error_details = Column(JSON, nullable=True)

    video = relationship("Video", back_populates="transcription_jobs")


class SummarizationJob(LeasedJobMixin, Base):
    """Summarization job model."""

    __tablename__ = "summarization_jobs"
    __table_args__ = (Index("ix_summarization_jobs_status_created_at", "status", "created_at"),)

    id = Column(String, primary_key=True, default=generate_uuid)
    transcript_id = Column(String, ForeignKey("transcripts.id"), nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)
    error_details = Column(JSON, nullable=True)

    transcript = relationship("Transcript", back_populates="summarization_jobs")


class TranslatedTranscript(Base):
    """Translated transcript model."""

    __tablename__ = "translated_transcripts"
    __table_args__ = (
        UniqueConstraint(
            "transcript_id",
            "language",
            name="uq_translated_transcripts_transcript_language",
        ),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    transcript_id = Column(String, ForeignKey("transcripts.id"), nullable=False)
    language = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    segments = Column(JSON, nullable=True)
    status = Column(String, default="completed")
    created_at = Column(DateTime, default=datetime.utcnow)

    transcript = relationship("Transcript", back_populates="translations")


class TranslationJob(LeasedJobMixin, Base):
    """Translation job model."""

    __tablename__ = "translation_jobs"
    __table_args__ = (Index("ix_translation_jobs_status_created_at", "status", "created_at"),)

    id = Column(String, primary_key=True, default=generate_uuid)
    transcript_id = Column(String, ForeignKey("transcripts.id"), nullable=False)
    source_language = Column(String, nullable=True)
    target_language = Column(String, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)
    error_details = Column(JSON, nullable=True)

    transcript = relationship("Transcript", back_populates="translation_jobs")


class TranscriptSegmentSearch(Base):
    """Search projection for transcript segments."""

    __tablename__ = "transcript_segment_search"
    __table_args__ = (
        UniqueConstraint(
            "transcript_id",
            "segment_id",
            name="uq_transcript_segment_search_transcript_segment",
        ),
        Index("ix_transcript_segment_search_transcript_id", "transcript_id"),
        Index("ix_transcript_segment_search_video_id", "video_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    transcript_id = Column(String, ForeignKey("transcripts.id"), nullable=False)
    video_id = Column(String, ForeignKey("videos.id"), nullable=True)
    segment_id = Column(Integer, nullable=False)
    start_time = Column(Float, nullable=False, default=0)
    end_time = Column(Float, nullable=False, default=0)
    text = Column(Text, nullable=False)
    speaker = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transcript = relationship("Transcript", back_populates="search_segments")
