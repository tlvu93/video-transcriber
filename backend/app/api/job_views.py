from __future__ import annotations

from typing import Any, Dict, Literal, Mapping, Optional

from sqlalchemy.orm import Session

from backend.app.persistence.models import UnifiedJob

try:
    from fastapi import HTTPException
except ModuleNotFoundError:  # pragma: no cover - used only in stripped-down test envs
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str) -> None:
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail


LegacyJobType = Literal["summarization", "transcription", "translation"]


def translate_job_domain_error(error: ValueError) -> HTTPException:
    detail = str(error)
    status_code = 404 if "not found" in detail.lower() else 400
    return HTTPException(status_code=status_code, detail=detail)


def _coerce_unified_job(unified_job: UnifiedJob | Mapping[str, Any]) -> Dict[str, Any]:
    if isinstance(unified_job, UnifiedJob):
        return {
            "id": str(unified_job.id),
            "legacy_job_id": str(unified_job.legacy_job_id),
            "legacy_job_table": unified_job.legacy_job_table,
            "job_type": unified_job.job_type,
            "subject_type": unified_job.subject_type,
            "subject_id": str(unified_job.subject_id),
            "status": unified_job.status,
            "priority": int(unified_job.priority or 100),
            "payload": dict(unified_job.payload or {}),
            "progress": unified_job.progress,
            "attempt_count": int(unified_job.attempt_count or 0),
            "created_at": unified_job.created_at,
            "started_at": unified_job.started_at,
            "completed_at": unified_job.completed_at,
            "processing_time_seconds": unified_job.processing_time_seconds,
            "error_details": unified_job.error_details,
            "worker_id": unified_job.worker_id,
            "lease_expires_at": unified_job.lease_expires_at,
        }

    serialized_job = dict(unified_job)
    payload = serialized_job.get("payload")
    serialized_job["payload"] = dict(payload) if isinstance(payload, dict) else {}
    return serialized_job


def project_legacy_job(
    job_type: LegacyJobType,
    unified_job: UnifiedJob | Mapping[str, Any],
) -> Dict[str, Any]:
    serialized_job = _coerce_unified_job(unified_job)
    payload = serialized_job.get("payload") or {}

    response: Dict[str, Any] = {
        "id": str(serialized_job.get("legacy_job_id") or serialized_job["id"]),
        "status": serialized_job["status"],
        "created_at": serialized_job["created_at"],
        "started_at": serialized_job.get("started_at"),
        "completed_at": serialized_job.get("completed_at"),
        "processing_time_seconds": serialized_job.get("processing_time_seconds"),
        "error_details": serialized_job.get("error_details"),
        "worker_id": serialized_job.get("worker_id"),
        "lease_expires_at": serialized_job.get("lease_expires_at"),
    }

    subject_id = str(serialized_job.get("subject_id") or "")
    if job_type == "transcription":
        response["video_id"] = str(payload.get("video_id") or subject_id)
        return response

    response["transcript_id"] = str(payload.get("transcript_id") or subject_id)
    if job_type == "summarization":
        response["content_profile"] = payload.get("content_profile")
        return response

    response.update(
        {
            "source_language": payload.get("source_language"),
            "target_language": payload.get("target_language"),
            "style_guide": payload.get("style_guide"),
            "glossary_terms": payload.get("glossary_terms"),
        }
    )
    return response


def get_legacy_job_projection_or_404(
    db: Session,
    *,
    job_type: LegacyJobType,
    legacy_job_id: str,
) -> Dict[str, Any]:
    unified_job = (
        db.query(UnifiedJob)
        .filter(UnifiedJob.job_type == job_type, UnifiedJob.legacy_job_id == legacy_job_id)
        .first()
    )
    if unified_job is None:
        raise HTTPException(
            status_code=404,
            detail=f"{job_type.title()} job not found: {legacy_job_id}",
        )
    return project_legacy_job(job_type, unified_job)


def list_legacy_job_projections(
    db: Session,
    *,
    job_type: LegacyJobType,
    status: Optional[str] = None,
    subject_id: Optional[str] = None,
    limit: int,
    offset: int,
) -> tuple[list[Dict[str, Any]], int]:
    query = db.query(UnifiedJob).filter(UnifiedJob.job_type == job_type)
    if status:
        query = query.filter(UnifiedJob.status == status)
    if subject_id:
        query = query.filter(UnifiedJob.subject_id == subject_id)

    query = query.order_by(UnifiedJob.created_at.desc(), UnifiedJob.id.desc())
    total = query.order_by(None).count()
    jobs = query.limit(limit).offset(offset).all()
    return [project_legacy_job(job_type, job) for job in jobs], total
