import uuid
from datetime import UTC, datetime

from backend.app.domain.canonical_metadata import (
    build_glossary_terms_snapshot,
    build_segments_snapshot_from_rows,
    build_speaker_alias_snapshot,
    normalize_glossary_terms,
    normalize_speaker_aliases,
    normalize_style_guide,
    resolve_primary_storage_uri,
)
from backend.app.persistence.database import Base
from sqlalchemy import Boolean, JSON, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship


_COMPAT_UNSET = object()


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def generate_uuid():
    """Generate a UUID for use as a primary key."""
    return str(uuid.uuid4())


class LeasedJobMixin:
    """Common lease state shared by all queue-backed jobs."""

    worker_id = Column(String, nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)


class UnifiedJob(LeasedJobMixin, Base):
    """Canonical orchestration record with compatibility IDs for legacy routes."""

    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("legacy_job_table", "legacy_job_id", name="uq_jobs_legacy_job"),
        Index("ix_jobs_job_type_status_created_at", "job_type", "status", "created_at"),
        Index("ix_jobs_subject_type_subject_id", "subject_type", "subject_id"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    legacy_job_table = Column(String, nullable=False)
    legacy_job_id = Column(String, nullable=False)
    job_type = Column(String, nullable=False)
    subject_type = Column(String, nullable=False)
    subject_id = Column(String, nullable=False)
    status = Column(String, default="pending")
    priority = Column(Integer, default=100)
    payload = Column(JSON, nullable=True)
    progress = Column(Float, nullable=True)
    attempt_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)
    error_details = Column(JSON, nullable=True)

    attempts = relationship(
        "JobAttempt",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobAttempt.attempt_number.desc()",
    )


class JobAttempt(Base):
    """One processing attempt for a unified job."""

    __tablename__ = "job_attempts"
    __table_args__ = (
        UniqueConstraint("job_id", "attempt_number", name="uq_job_attempts_job_attempt_number"),
        Index("ix_job_attempts_job_id_created_at", "job_id", "created_at"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    attempt_number = Column(Integer, nullable=False)
    worker_id = Column(String, nullable=True)
    status = Column(String, default="processing")
    started_at = Column(DateTime, default=_utcnow)
    completed_at = Column(DateTime, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)
    error_details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    job = relationship("UnifiedJob", back_populates="attempts")


class Video(Base):
    """Video model."""

    __tablename__ = "videos"
    __table_args__ = (
        Index("ix_videos_filename", "filename"),
        Index("ix_videos_file_hash", "file_hash"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    filename = Column(String, nullable=False)
    file_hash = Column(String, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=_utcnow)
    video_metadata = Column(JSON, default=dict)

    transcripts = relationship("Transcript", back_populates="video")
    storage_objects = relationship(
        "VideoStorageObject",
        back_populates="video",
        cascade="all, delete-orphan",
        order_by="VideoStorageObject.created_at.desc()",
    )

    def __init__(self, **kwargs):
        storage_path = kwargs.pop("storage_path", _COMPAT_UNSET)
        super().__init__(**kwargs)
        if storage_path is not _COMPAT_UNSET:
            self.storage_path = storage_path

    @property
    def storage_path(self):
        override = getattr(self, "_storage_path_override", _COMPAT_UNSET)
        if override is not _COMPAT_UNSET:
            return override
        return resolve_primary_storage_uri(self.storage_objects or [])

    @storage_path.setter
    def storage_path(self, value):
        normalized_value = str(value).strip() if value is not None else None
        self._storage_path_override = normalized_value or None


class VideoStorageObject(Base):
    """Normalized storage identity for a video asset."""

    __tablename__ = "video_storage_objects"
    __table_args__ = (
        UniqueConstraint(
            "storage_backend",
            "storage_uri",
            name="uq_video_storage_objects_backend_uri",
        ),
        Index("ix_video_storage_objects_video_primary", "video_id", "is_primary"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    video_id = Column(String, ForeignKey("videos.id"), nullable=False)
    storage_backend = Column(String, nullable=False, default="local_fs")
    storage_uri = Column(String, nullable=False)
    content_hash = Column(String, nullable=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    video = relationship("Video", back_populates="storage_objects")


class Transcript(Base):
    """Transcript model."""

    __tablename__ = "transcripts"
    __table_args__ = (
        Index("ix_transcripts_video_id", "video_id"),
        Index("ix_transcripts_language_code", "language_code"),
        Index("ix_transcripts_review_status", "review_status"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    video_id = Column(String, ForeignKey("videos.id"), nullable=True)
    source_type = Column(String, default="video")
    content = Column(Text, nullable=False)
    format = Column(String, default="txt")
    status = Column(String, default="pending")
    language_code = Column(String, nullable=True)
    review_status = Column(String, default="draft")
    review_assignee = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    video = relationship("Video", back_populates="transcripts")
    revisions = relationship(
        "TranscriptRevision",
        back_populates="transcript",
        cascade="all, delete-orphan",
        order_by="TranscriptRevision.revision_number.desc()",
    )
    segment_rows = relationship(
        "TranscriptSegmentRow",
        back_populates="transcript",
        cascade="all, delete-orphan",
        order_by="TranscriptSegmentRow.segment_index.asc()",
    )
    summaries = relationship("Summary", back_populates="transcript")
    translations = relationship("TranslatedTranscript", back_populates="transcript")
    search_segments = relationship(
        "TranscriptSegmentSearch",
        back_populates="transcript",
        cascade="all, delete-orphan",
    )
    comments = relationship(
        "TranscriptComment",
        back_populates="transcript",
        cascade="all, delete-orphan",
        order_by="TranscriptComment.created_at.desc()",
    )
    speakers = relationship(
        "Speaker",
        back_populates="transcript",
        cascade="all, delete-orphan",
        order_by="Speaker.speaker_key.asc()",
    )

    def __init__(self, **kwargs):
        segments = kwargs.pop("segments", _COMPAT_UNSET)
        speaker_aliases = kwargs.pop("speaker_aliases", _COMPAT_UNSET)
        super().__init__(**kwargs)
        if segments is not _COMPAT_UNSET:
            self.segments = segments
        if speaker_aliases is not _COMPAT_UNSET:
            self.speaker_aliases = speaker_aliases

    @property
    def segments(self):
        override = getattr(self, "_segments_override", _COMPAT_UNSET)
        if override is not _COMPAT_UNSET:
            return override
        if self.segment_rows:
            return build_segments_snapshot_from_rows(self.segment_rows)
        return None

    @segments.setter
    def segments(self, value):
        self._segments_override = value if isinstance(value, list) else None

    @property
    def speaker_aliases(self):
        override = getattr(self, "_speaker_aliases_override", _COMPAT_UNSET)
        if override is not _COMPAT_UNSET:
            return override
        if self.speakers:
            return build_speaker_alias_snapshot(self.speakers)
        return {}

    @speaker_aliases.setter
    def speaker_aliases(self, value):
        self._speaker_aliases_override = normalize_speaker_aliases(value)


class TranscriptRevision(Base):
    """Immutable snapshot of transcript edits over time."""

    __tablename__ = "transcript_revisions"
    __table_args__ = (
        UniqueConstraint(
            "transcript_id",
            "revision_number",
            name="uq_transcript_revisions_transcript_revision_number",
        ),
        Index("ix_transcript_revisions_transcript_created_at", "transcript_id", "created_at"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    transcript_id = Column(String, ForeignKey("transcripts.id"), nullable=False)
    revision_number = Column(Integer, nullable=False)
    reason = Column(String, nullable=False, default="manual_edit")
    content = Column(Text, nullable=False)
    segments = Column(JSON, nullable=True)
    speaker_aliases = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    transcript = relationship("Transcript", back_populates="revisions")


class TranscriptComment(Base):
    """Timestamp-linked review comment on a transcript."""

    __tablename__ = "transcript_comments"
    __table_args__ = (
        Index("ix_transcript_comments_transcript_created_at", "transcript_id", "created_at"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    transcript_id = Column(String, ForeignKey("transcripts.id"), nullable=False)
    segment_id = Column(Integer, nullable=True)
    timestamp_seconds = Column(Float, nullable=True)
    author_name = Column(String, nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    transcript = relationship("Transcript", back_populates="comments")


class TranscriptSegmentRow(Base):
    """Normalized row form of transcript segments."""

    __tablename__ = "transcript_segments"
    __table_args__ = (
        UniqueConstraint(
            "transcript_id",
            "segment_id",
            name="uq_transcript_segments_transcript_segment",
        ),
        Index("ix_transcript_segments_transcript_index", "transcript_id", "segment_index"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    transcript_id = Column(String, ForeignKey("transcripts.id"), nullable=False)
    segment_id = Column(Integer, nullable=False)
    segment_index = Column(Integer, nullable=False)
    start_time = Column(Float, nullable=False, default=0)
    end_time = Column(Float, nullable=False, default=0)
    text = Column(Text, nullable=False)
    speaker = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    transcript = relationship("Transcript", back_populates="segment_rows")


class Speaker(Base):
    """Normalized per-transcript speaker alias record."""

    __tablename__ = "speakers"
    __table_args__ = (
        UniqueConstraint(
            "transcript_id",
            "speaker_key",
            name="uq_speakers_transcript_key",
        ),
        Index("ix_speakers_transcript_display_name", "transcript_id", "display_name"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    transcript_id = Column(String, ForeignKey("transcripts.id"), nullable=False)
    speaker_key = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    transcript = relationship("Transcript", back_populates="speakers")


class Summary(Base):
    """Summary model."""

    __tablename__ = "summaries"

    id = Column(String, primary_key=True, default=generate_uuid)
    transcript_id = Column(String, ForeignKey("transcripts.id"), nullable=False)
    content = Column(Text, nullable=False)
    content_profile = Column(String, nullable=False, default="generic")
    summary_metadata = Column(JSON, nullable=True)
    status = Column(String, default="pending")  # pending, completed, error
    created_at = Column(DateTime, default=_utcnow)

    transcript = relationship("Transcript", back_populates="summaries")
    variants = relationship(
        "SummaryVariant",
        back_populates="summary",
        cascade="all, delete-orphan",
        order_by="SummaryVariant.created_at.desc()",
    )


class SummaryVariant(Base):
    """Named summary rendering variant for a summary record."""

    __tablename__ = "summary_variants"
    __table_args__ = (
        UniqueConstraint(
            "summary_id",
            "variant_type",
            name="uq_summary_variants_summary_variant_type",
        ),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    summary_id = Column(String, ForeignKey("summaries.id"), nullable=False)
    variant_type = Column(String, nullable=False, default="default")
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    summary = relationship("Summary", back_populates="variants")


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
    qa_metrics = Column(JSON, nullable=True)
    status = Column(String, default="completed")
    created_at = Column(DateTime, default=_utcnow)

    transcript = relationship("Transcript", back_populates="translations")
    segment_rows = relationship(
        "TranslatedTranscriptSegmentRow",
        back_populates="translated_transcript",
        cascade="all, delete-orphan",
        order_by="TranslatedTranscriptSegmentRow.segment_index.asc()",
    )
    style_guide_row = relationship(
        "StyleGuide",
        back_populates="translated_transcript",
        cascade="all, delete-orphan",
        uselist=False,
    )
    glossary_term_rows = relationship(
        "GlossaryTerm",
        back_populates="translated_transcript",
        cascade="all, delete-orphan",
        order_by="GlossaryTerm.sort_order.asc()",
    )

    def __init__(self, **kwargs):
        segments = kwargs.pop("segments", _COMPAT_UNSET)
        style_guide = kwargs.pop("style_guide", _COMPAT_UNSET)
        glossary_terms = kwargs.pop("glossary_terms", _COMPAT_UNSET)
        super().__init__(**kwargs)
        if segments is not _COMPAT_UNSET:
            self.segments = segments
        if style_guide is not _COMPAT_UNSET:
            self.style_guide = style_guide
        if glossary_terms is not _COMPAT_UNSET:
            self.glossary_terms = glossary_terms

    @property
    def segments(self):
        override = getattr(self, "_segments_override", _COMPAT_UNSET)
        if override is not _COMPAT_UNSET:
            return override
        if self.segment_rows:
            return build_segments_snapshot_from_rows(self.segment_rows)
        return None

    @segments.setter
    def segments(self, value):
        self._segments_override = value if isinstance(value, list) else None

    @property
    def style_guide(self):
        override = getattr(self, "_style_guide_override", _COMPAT_UNSET)
        if override is not _COMPAT_UNSET:
            return override
        if self.style_guide_row is not None:
            return self.style_guide_row.content
        return None

    @style_guide.setter
    def style_guide(self, value):
        self._style_guide_override = normalize_style_guide(value)

    @property
    def glossary_terms(self):
        override = getattr(self, "_glossary_terms_override", _COMPAT_UNSET)
        if override is not _COMPAT_UNSET:
            return override
        if self.glossary_term_rows:
            return build_glossary_terms_snapshot(self.glossary_term_rows)
        return []

    @glossary_terms.setter
    def glossary_terms(self, value):
        self._glossary_terms_override = normalize_glossary_terms(value)


class TranslatedTranscriptSegmentRow(Base):
    """Normalized row form of translated transcript segments."""

    __tablename__ = "translated_transcript_segments"
    __table_args__ = (
        UniqueConstraint(
            "translated_transcript_id",
            "segment_id",
            name="uq_translated_transcript_segments_segment",
        ),
        Index(
            "ix_translated_transcript_segments_transcript_index",
            "translated_transcript_id",
            "segment_index",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    translated_transcript_id = Column(
        String,
        ForeignKey("translated_transcripts.id"),
        nullable=False,
    )
    segment_id = Column(Integer, nullable=False)
    segment_index = Column(Integer, nullable=False)
    start_time = Column(Float, nullable=False, default=0)
    end_time = Column(Float, nullable=False, default=0)
    text = Column(Text, nullable=False)
    speaker = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    translated_transcript = relationship(
        "TranslatedTranscript",
        back_populates="segment_rows",
    )


class StyleGuide(Base):
    """Normalized style guide associated with a translated transcript."""

    __tablename__ = "style_guides"
    __table_args__ = (
        UniqueConstraint(
            "translated_transcript_id",
            name="uq_style_guides_translated_transcript",
        ),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    translated_transcript_id = Column(
        String,
        ForeignKey("translated_transcripts.id"),
        nullable=False,
    )
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    translated_transcript = relationship(
        "TranslatedTranscript",
        back_populates="style_guide_row",
    )


class GlossaryTerm(Base):
    """Normalized glossary term associated with a translated transcript."""

    __tablename__ = "glossary_terms"
    __table_args__ = (
        Index(
            "ix_glossary_terms_translated_transcript_sort",
            "translated_transcript_id",
            "sort_order",
        ),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    translated_transcript_id = Column(
        String,
        ForeignKey("translated_transcripts.id"),
        nullable=False,
    )
    source_term = Column(String, nullable=False)
    target_term = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    translated_transcript = relationship(
        "TranslatedTranscript",
        back_populates="glossary_term_rows",
    )


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
        Index("ix_transcript_segment_search_speaker", "speaker"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    transcript_id = Column(String, ForeignKey("transcripts.id"), nullable=False)
    video_id = Column(String, ForeignKey("videos.id"), nullable=True)
    segment_id = Column(Integer, nullable=False)
    start_time = Column(Float, nullable=False, default=0)
    end_time = Column(Float, nullable=False, default=0)
    text = Column(Text, nullable=False)
    speaker = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    transcript = relationship("Transcript", back_populates="search_segments")


class OperationalMetricEvent(Base):
    """Persisted operational metric sample emitted by API or worker processes."""

    __tablename__ = "operational_metric_events"
    __table_args__ = (
        Index("ix_operational_metric_events_name_recorded_at", "metric_name", "recorded_at"),
        Index("ix_operational_metric_events_source_recorded_at", "metric_source", "recorded_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_name = Column(String, nullable=False)
    metric_source = Column(String, nullable=False)
    metric_value = Column(Float, nullable=False, default=0)
    labels = Column(JSON, nullable=True)
    recorded_at = Column(DateTime, default=_utcnow, nullable=False)
