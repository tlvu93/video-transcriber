from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

LegacyJobType = Literal["summarization", "transcription", "translation"]


class LeaseWorkerRequest(BaseModel):
    worker_id: str


class TranscriptionJobCreate(BaseModel):
    video_id: str


class TranscriptionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    video_id: str
    status: str
    created_at: Any
    started_at: Any | None = None
    completed_at: Any | None = None
    processing_time_seconds: float | None = None
    error_details: dict[str, Any] | None = None
    worker_id: str | None = None
    lease_expires_at: Any | None = None


class TranscriptionJobUpdate(LeaseWorkerRequest):
    status: str | None = None
    processing_time_seconds: float | None = None
    error_details: dict[str, Any] | None = None


class SummarizationJobCreate(BaseModel):
    transcript_id: str
    content_profile: Literal["generic", "interview", "lecture", "meeting", "podcast"] | None = None


class SummarizationJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    transcript_id: str
    content_profile: str | None = None
    status: str
    created_at: Any
    started_at: Any | None = None
    completed_at: Any | None = None
    processing_time_seconds: float | None = None
    error_details: dict[str, Any] | None = None
    worker_id: str | None = None
    lease_expires_at: Any | None = None


class SummarizationJobUpdate(LeaseWorkerRequest):
    status: str | None = None
    processing_time_seconds: float | None = None
    error_details: dict[str, Any] | None = None


class TranslationGlossaryTermInput(BaseModel):
    source_term: str
    target_term: str
    notes: str | None = None


def normalize_translation_glossary_terms(
    raw_terms: list[TranslationGlossaryTermInput] | None,
) -> list[dict[str, str]]:
    normalized_terms: list[dict[str, str]] = []
    for raw_term in raw_terms or []:
        source_term = raw_term.source_term.strip()
        target_term = raw_term.target_term.strip()
        if not source_term or not target_term:
            continue

        normalized_term = {
            "source_term": source_term,
            "target_term": target_term,
        }
        if raw_term.notes and raw_term.notes.strip():
            normalized_term["notes"] = raw_term.notes.strip()

        normalized_terms.append(normalized_term)

    return normalized_terms


class TranslationJobCreate(BaseModel):
    transcript_id: str
    target_language: str
    source_language: str | None = None
    style_guide: str | None = None
    glossary_terms: list[TranslationGlossaryTermInput] | None = None


class TranslationJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    transcript_id: str
    source_language: str | None
    target_language: str
    style_guide: str | None = None
    glossary_terms: list[dict[str, str]] | None = None
    status: str
    created_at: Any
    started_at: Any | None = None
    completed_at: Any | None = None
    processing_time_seconds: float | None = None
    error_details: dict[str, Any] | None = None
    worker_id: str | None = None
    lease_expires_at: Any | None = None


class TranslationJobUpdate(LeaseWorkerRequest):
    status: str | None = None
    processing_time_seconds: float | None = None
    error_details: dict[str, Any] | None = None


class UnifiedJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    legacy_job_table: str
    legacy_job_id: str
    job_type: str
    subject_type: str
    subject_id: str
    status: str
    priority: int
    payload: dict[str, Any] | None = None
    progress: float | None = None
    attempt_count: int
    worker_id: str | None = None
    lease_expires_at: Any | None = None
    created_at: Any
    started_at: Any | None = None
    completed_at: Any | None = None
    processing_time_seconds: float | None = None
    error_details: dict[str, Any] | None = None


class JobAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    attempt_number: int
    worker_id: str | None = None
    status: str
    started_at: Any
    completed_at: Any | None = None
    processing_time_seconds: float | None = None
    error_details: dict[str, Any] | None = None
    created_at: Any
