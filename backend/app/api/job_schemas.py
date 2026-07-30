from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

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
    started_at: Optional[Any] = None
    completed_at: Optional[Any] = None
    processing_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None
    worker_id: Optional[str] = None
    lease_expires_at: Optional[Any] = None


class TranscriptionJobUpdate(LeaseWorkerRequest):
    status: Optional[str] = None
    processing_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None


class SummarizationJobCreate(BaseModel):
    transcript_id: str
    content_profile: Optional[
        Literal["generic", "interview", "lecture", "meeting", "podcast"]
    ] = None


class SummarizationJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    transcript_id: str
    content_profile: Optional[str] = None
    status: str
    created_at: Any
    started_at: Optional[Any] = None
    completed_at: Optional[Any] = None
    processing_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None
    worker_id: Optional[str] = None
    lease_expires_at: Optional[Any] = None


class SummarizationJobUpdate(LeaseWorkerRequest):
    status: Optional[str] = None
    processing_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None


class TranslationGlossaryTermInput(BaseModel):
    source_term: str
    target_term: str
    notes: Optional[str] = None


def normalize_translation_glossary_terms(
    raw_terms: Optional[List[TranslationGlossaryTermInput]],
) -> List[Dict[str, str]]:
    normalized_terms: List[Dict[str, str]] = []
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
    source_language: Optional[str] = None
    style_guide: Optional[str] = None
    glossary_terms: Optional[List[TranslationGlossaryTermInput]] = None


class TranslationJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    transcript_id: str
    source_language: Optional[str]
    target_language: str
    style_guide: Optional[str] = None
    glossary_terms: Optional[List[Dict[str, str]]] = None
    status: str
    created_at: Any
    started_at: Optional[Any] = None
    completed_at: Optional[Any] = None
    processing_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None
    worker_id: Optional[str] = None
    lease_expires_at: Optional[Any] = None


class TranslationJobUpdate(LeaseWorkerRequest):
    status: Optional[str] = None
    processing_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None


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
    payload: Optional[Dict[str, Any]] = None
    progress: Optional[float] = None
    attempt_count: int
    worker_id: Optional[str] = None
    lease_expires_at: Optional[Any] = None
    created_at: Any
    started_at: Optional[Any] = None
    completed_at: Optional[Any] = None
    processing_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None


class JobAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    attempt_number: int
    worker_id: Optional[str] = None
    status: str
    started_at: Any
    completed_at: Optional[Any] = None
    processing_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None
    created_at: Any
