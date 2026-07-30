from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.api.common import PaginatedResponse, build_paginated_response, paginate_query
from backend.app.api.job_schemas import (
    JobAttemptResponse,
    LeaseWorkerRequest,
    SummarizationJobCreate,
    SummarizationJobResponse,
    SummarizationJobUpdate,
    TranscriptionJobCreate,
    TranscriptionJobResponse,
    TranscriptionJobUpdate,
    TranslationJobCreate,
    TranslationJobResponse,
    TranslationJobUpdate,
    UnifiedJobResponse,
    normalize_translation_glossary_terms,
)
from backend.app.api.job_views import (
    get_legacy_job_projection_or_404,
    list_legacy_job_projections,
    project_legacy_job,
    translate_job_domain_error,
)
from backend.app.domain.jobs import (
    JobLeaseOwnershipError,
    claim_next_summarization_job,
    claim_next_transcription_job,
    claim_next_translation_job,
    complete_legacy_job,
    create_summarization_job_for_transcript,
    create_transcription_job_for_video,
    create_translation_job_for_transcript,
    fail_legacy_job,
    heartbeat_legacy_job,
    request_job_cancellation,
    retry_job,
    retry_legacy_job,
)
from backend.app.domain.records import normalize_translation_style_guide
from backend.app.persistence.database import get_db
from backend.app.persistence.models import JobAttempt, Transcript, UnifiedJob, Video

logger = logging.getLogger("api.jobs")
router = APIRouter()


@router.post("/transcription-jobs/", response_model=TranscriptionJobResponse)
async def create_transcription_job_endpoint(
    job_data: TranscriptionJobCreate,
    db: Session = Depends(get_db),
):
    logger.info("Creating transcription job for video: %s", job_data.video_id)
    video = db.query(Video).filter(Video.id == job_data.video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail=f"Video not found: {job_data.video_id}")

    try:
        unified_job = create_transcription_job_for_video(job_data.video_id)
    except ValueError as error:
        raise translate_job_domain_error(error) from error

    return project_legacy_job("transcription", unified_job)


@router.post("/transcription-jobs/claim", response_model=TranscriptionJobResponse | None)
async def claim_transcription_job(
    request_data: LeaseWorkerRequest,
    db: Session = Depends(get_db),
):
    del db
    unified_job = claim_next_transcription_job(request_data.worker_id)
    if not unified_job:
        return None
    return project_legacy_job("transcription", unified_job)


@router.post("/transcription-jobs/{job_id}/heartbeat", response_model=TranscriptionJobResponse)
async def heartbeat_transcription_job(
    job_id: str,
    request_data: LeaseWorkerRequest,
    db: Session = Depends(get_db),
):
    try:
        heartbeat_legacy_job("transcription", job_id, request_data.worker_id)
    except JobLeaseOwnershipError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise translate_job_domain_error(error) from error
    return get_legacy_job_projection_or_404(db, job_type="transcription", legacy_job_id=job_id)


@router.get("/transcription-jobs", response_model=PaginatedResponse[TranscriptionJobResponse])
async def get_transcription_jobs(
    status: str | None = None,
    video_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    jobs, total = list_legacy_job_projections(
        db,
        job_type="transcription",
        status=status,
        subject_id=video_id,
        limit=limit,
        offset=offset,
    )
    return build_paginated_response(jobs, total=total, limit=limit, offset=offset)


@router.get("/transcription-jobs/{job_id}", response_model=TranscriptionJobResponse)
async def get_transcription_job(job_id: str, db: Session = Depends(get_db)):
    return get_legacy_job_projection_or_404(db, job_type="transcription", legacy_job_id=job_id)


@router.post("/transcription-jobs/{job_id}/complete", response_model=TranscriptionJobResponse)
async def complete_transcription_job(
    job_id: str,
    update_data: TranscriptionJobUpdate,
    db: Session = Depends(get_db),
):
    try:
        complete_legacy_job(
            "transcription",
            job_id,
            update_data.worker_id,
            processing_time=update_data.processing_time_seconds,
            error_details=update_data.error_details,
        )
    except JobLeaseOwnershipError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise translate_job_domain_error(error) from error
    return get_legacy_job_projection_or_404(db, job_type="transcription", legacy_job_id=job_id)


@router.post("/transcription-jobs/{job_id}/fail", response_model=TranscriptionJobResponse)
async def fail_transcription_job(
    job_id: str,
    update_data: TranscriptionJobUpdate,
    db: Session = Depends(get_db),
):
    try:
        fail_legacy_job(
            "transcription",
            job_id,
            update_data.worker_id,
            error_details=update_data.error_details,
        )
    except JobLeaseOwnershipError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise translate_job_domain_error(error) from error
    return get_legacy_job_projection_or_404(db, job_type="transcription", legacy_job_id=job_id)


@router.post("/transcription-jobs/{job_id}/retry", response_model=TranscriptionJobResponse)
async def retry_transcription_job(job_id: str, db: Session = Depends(get_db)):
    try:
        retry_legacy_job("transcription", job_id)
    except ValueError as error:
        raise translate_job_domain_error(error) from error

    logger.info("Transcription job %s has been reset to pending status for retry", job_id)
    return get_legacy_job_projection_or_404(db, job_type="transcription", legacy_job_id=job_id)


@router.post("/summarization-jobs/", response_model=SummarizationJobResponse)
async def create_summarization_job_endpoint(
    job_data: SummarizationJobCreate,
    db: Session = Depends(get_db),
):
    logger.info("Creating summarization job for transcript: %s", job_data.transcript_id)
    transcript = db.query(Transcript).filter(Transcript.id == job_data.transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail=f"Transcript not found: {job_data.transcript_id}")

    try:
        unified_job = create_summarization_job_for_transcript(
            job_data.transcript_id,
            content_profile=job_data.content_profile,
        )
    except ValueError as error:
        raise translate_job_domain_error(error) from error

    return project_legacy_job("summarization", unified_job)


@router.post("/summarization-jobs/claim", response_model=SummarizationJobResponse | None)
async def claim_summarization_job(
    request_data: LeaseWorkerRequest,
    db: Session = Depends(get_db),
):
    del db
    unified_job = claim_next_summarization_job(request_data.worker_id)
    if not unified_job:
        return None
    return project_legacy_job("summarization", unified_job)


@router.post("/summarization-jobs/{job_id}/heartbeat", response_model=SummarizationJobResponse)
async def heartbeat_summarization_job(
    job_id: str,
    request_data: LeaseWorkerRequest,
    db: Session = Depends(get_db),
):
    try:
        heartbeat_legacy_job("summarization", job_id, request_data.worker_id)
    except JobLeaseOwnershipError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise translate_job_domain_error(error) from error
    return get_legacy_job_projection_or_404(db, job_type="summarization", legacy_job_id=job_id)


@router.get("/summarization-jobs", response_model=PaginatedResponse[SummarizationJobResponse])
async def get_summarization_jobs(
    status: str | None = None,
    transcript_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    jobs, total = list_legacy_job_projections(
        db,
        job_type="summarization",
        status=status,
        subject_id=transcript_id,
        limit=limit,
        offset=offset,
    )
    return build_paginated_response(jobs, total=total, limit=limit, offset=offset)


@router.get("/summarization-jobs/{job_id}", response_model=SummarizationJobResponse)
async def get_summarization_job(job_id: str, db: Session = Depends(get_db)):
    return get_legacy_job_projection_or_404(db, job_type="summarization", legacy_job_id=job_id)


@router.post("/summarization-jobs/{job_id}/complete", response_model=SummarizationJobResponse)
async def complete_summarization_job(
    job_id: str,
    update_data: SummarizationJobUpdate,
    db: Session = Depends(get_db),
):
    try:
        complete_legacy_job(
            "summarization",
            job_id,
            update_data.worker_id,
            processing_time=update_data.processing_time_seconds,
            error_details=update_data.error_details,
        )
    except JobLeaseOwnershipError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise translate_job_domain_error(error) from error
    return get_legacy_job_projection_or_404(db, job_type="summarization", legacy_job_id=job_id)


@router.post("/summarization-jobs/{job_id}/fail", response_model=SummarizationJobResponse)
async def fail_summarization_job(
    job_id: str,
    update_data: SummarizationJobUpdate,
    db: Session = Depends(get_db),
):
    try:
        fail_legacy_job(
            "summarization",
            job_id,
            update_data.worker_id,
            error_details=update_data.error_details,
        )
    except JobLeaseOwnershipError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise translate_job_domain_error(error) from error
    return get_legacy_job_projection_or_404(db, job_type="summarization", legacy_job_id=job_id)


@router.post("/translation-jobs/", response_model=TranslationJobResponse)
async def create_translation_job_endpoint(
    job_data: TranslationJobCreate,
    db: Session = Depends(get_db),
):
    logger.info(
        "Creating translation job for transcript: %s to %s",
        job_data.transcript_id,
        job_data.target_language,
    )
    transcript = db.query(Transcript).filter(Transcript.id == job_data.transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail=f"Transcript not found: {job_data.transcript_id}")

    style_guide = normalize_translation_style_guide(job_data.style_guide)
    glossary_terms = normalize_translation_glossary_terms(job_data.glossary_terms)

    try:
        unified_job = create_translation_job_for_transcript(
            job_data.transcript_id,
            job_data.target_language,
            job_data.source_language,
            style_guide=style_guide,
            glossary_terms=glossary_terms,
        )
    except ValueError as error:
        raise translate_job_domain_error(error) from error

    return project_legacy_job("translation", unified_job)


@router.post("/translation-jobs/claim", response_model=TranslationJobResponse | None)
async def claim_translation_job(
    request_data: LeaseWorkerRequest,
    db: Session = Depends(get_db),
):
    del db
    unified_job = claim_next_translation_job(request_data.worker_id)
    if not unified_job:
        return None
    return project_legacy_job("translation", unified_job)


@router.post("/translation-jobs/{job_id}/heartbeat", response_model=TranslationJobResponse)
async def heartbeat_translation_job(
    job_id: str,
    request_data: LeaseWorkerRequest,
    db: Session = Depends(get_db),
):
    try:
        heartbeat_legacy_job("translation", job_id, request_data.worker_id)
    except JobLeaseOwnershipError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise translate_job_domain_error(error) from error
    return get_legacy_job_projection_or_404(db, job_type="translation", legacy_job_id=job_id)


@router.get("/translation-jobs", response_model=PaginatedResponse[TranslationJobResponse])
async def get_translation_jobs(
    status: str | None = None,
    transcript_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    jobs, total = list_legacy_job_projections(
        db,
        job_type="translation",
        status=status,
        subject_id=transcript_id,
        limit=limit,
        offset=offset,
    )
    return build_paginated_response(jobs, total=total, limit=limit, offset=offset)


@router.get("/translation-jobs/{job_id}", response_model=TranslationJobResponse)
async def get_translation_job(job_id: str, db: Session = Depends(get_db)):
    return get_legacy_job_projection_or_404(db, job_type="translation", legacy_job_id=job_id)


@router.get("/jobs", response_model=PaginatedResponse[UnifiedJobResponse])
def list_unified_jobs(
    job_type: Literal["summarization", "transcription", "translation"] | None = None,
    status: str | None = None,
    subject_type: Literal["transcript", "video"] | None = None,
    subject_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(UnifiedJob)
    if job_type:
        query = query.filter(UnifiedJob.job_type == job_type)
    if status:
        query = query.filter(UnifiedJob.status == status)
    if subject_type:
        query = query.filter(UnifiedJob.subject_type == subject_type)
    if subject_id:
        query = query.filter(UnifiedJob.subject_id == subject_id)

    query = query.order_by(UnifiedJob.created_at.desc(), UnifiedJob.id.desc())
    jobs, total = paginate_query(query, limit=limit, offset=offset)
    return build_paginated_response(jobs, total=total, limit=limit, offset=offset)


@router.get("/jobs/{job_id}", response_model=UnifiedJobResponse)
def get_unified_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(UnifiedJob).filter(UnifiedJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/{job_id}/attempts", response_model=list[JobAttemptResponse])
def list_job_attempts(job_id: str, db: Session = Depends(get_db)):
    job = db.query(UnifiedJob).filter(UnifiedJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return (
        db.query(JobAttempt)
        .filter(JobAttempt.job_id == job_id)
        .order_by(JobAttempt.attempt_number.desc(), JobAttempt.created_at.desc())
        .all()
    )


@router.post("/jobs/{job_id}/cancel", response_model=UnifiedJobResponse)
def cancel_unified_job(job_id: str):
    try:
        return request_job_cancellation(job_id)
    except ValueError as error:
        raise translate_job_domain_error(error) from error


@router.post("/jobs/{job_id}/retry", response_model=UnifiedJobResponse)
def retry_unified_job(job_id: str):
    try:
        return retry_job(job_id)
    except ValueError as error:
        raise translate_job_domain_error(error) from error


@router.post("/translation-jobs/{job_id}/complete", response_model=TranslationJobResponse)
async def complete_translation_job(
    job_id: str,
    update_data: TranslationJobUpdate,
    db: Session = Depends(get_db),
):
    try:
        complete_legacy_job(
            "translation",
            job_id,
            update_data.worker_id,
            processing_time=update_data.processing_time_seconds,
            error_details=update_data.error_details,
        )
    except JobLeaseOwnershipError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise translate_job_domain_error(error) from error
    return get_legacy_job_projection_or_404(db, job_type="translation", legacy_job_id=job_id)


@router.post("/translation-jobs/{job_id}/fail", response_model=TranslationJobResponse)
async def fail_translation_job(
    job_id: str,
    update_data: TranslationJobUpdate,
    db: Session = Depends(get_db),
):
    try:
        fail_legacy_job(
            "translation",
            job_id,
            update_data.worker_id,
            error_details=update_data.error_details,
        )
    except JobLeaseOwnershipError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise translate_job_domain_error(error) from error
    return get_legacy_job_projection_or_404(db, job_type="translation", legacy_job_id=job_id)
