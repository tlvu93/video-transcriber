from datetime import datetime

from backend.app.api.job_views import (
    get_legacy_job_projection_or_404,
    list_legacy_job_projections,
    project_legacy_job,
)
from backend.app.persistence.models import UnifiedJob


def test_project_legacy_translation_job_uses_unified_payload(db_session):
    job = UnifiedJob(
        id="job-translation-1",
        legacy_job_table="translation_jobs",
        legacy_job_id="legacy-translation-1",
        job_type="translation",
        subject_type="transcript",
        subject_id="transcript-1",
        status="processing",
        payload={
            "transcript_id": "transcript-1",
            "source_language": "en",
            "target_language": "fr",
            "style_guide": "Formal tone",
            "glossary_terms": [{"source_term": "AI", "target_term": "IA"}],
        },
        created_at=datetime(2026, 3, 15, 10, 0, 0),
        worker_id="worker-1",
    )

    projected = project_legacy_job("translation", job)

    assert projected == {
        "id": "legacy-translation-1",
        "transcript_id": "transcript-1",
        "source_language": "en",
        "target_language": "fr",
        "style_guide": "Formal tone",
        "glossary_terms": [{"source_term": "AI", "target_term": "IA"}],
        "status": "processing",
        "created_at": datetime(2026, 3, 15, 10, 0, 0),
        "started_at": None,
        "completed_at": None,
        "processing_time_seconds": None,
        "error_details": None,
        "worker_id": "worker-1",
        "lease_expires_at": None,
    }


def test_list_legacy_job_projections_filters_unified_jobs(db_session):
    db_session.add_all(
        [
            UnifiedJob(
                id="job-1",
                legacy_job_table="transcription_jobs",
                legacy_job_id="legacy-1",
                job_type="transcription",
                subject_type="video",
                subject_id="video-1",
                status="pending",
                payload={"video_id": "video-1"},
                created_at=datetime(2026, 3, 15, 10, 0, 0),
            ),
            UnifiedJob(
                id="job-2",
                legacy_job_table="transcription_jobs",
                legacy_job_id="legacy-2",
                job_type="transcription",
                subject_type="video",
                subject_id="video-2",
                status="pending",
                payload={"video_id": "video-2"},
                created_at=datetime(2026, 3, 15, 11, 0, 0),
            ),
            UnifiedJob(
                id="job-3",
                legacy_job_table="transcription_jobs",
                legacy_job_id="legacy-3",
                job_type="transcription",
                subject_type="video",
                subject_id="video-1",
                status="completed",
                payload={"video_id": "video-1"},
                created_at=datetime(2026, 3, 15, 12, 0, 0),
            ),
        ]
    )
    db_session.commit()

    jobs, total = list_legacy_job_projections(
        db_session,
        job_type="transcription",
        status="pending",
        subject_id="video-1",
        limit=10,
        offset=0,
    )

    assert total == 1
    assert jobs == [
        {
            "id": "legacy-1",
            "video_id": "video-1",
            "status": "pending",
            "created_at": datetime(2026, 3, 15, 10, 0, 0),
            "started_at": None,
            "completed_at": None,
            "processing_time_seconds": None,
            "error_details": None,
            "worker_id": None,
            "lease_expires_at": None,
        }
    ]


def test_get_legacy_job_projection_or_404_reads_unified_store(db_session):
    db_session.add(
        UnifiedJob(
            id="job-summary-1",
            legacy_job_table="summarization_jobs",
            legacy_job_id="legacy-summary-1",
            job_type="summarization",
            subject_type="transcript",
            subject_id="transcript-9",
            status="completed",
            payload={
                "transcript_id": "transcript-9",
                "content_profile": "meeting",
            },
            created_at=datetime(2026, 3, 15, 9, 30, 0),
            completed_at=datetime(2026, 3, 15, 9, 45, 0),
            processing_time_seconds=900.0,
        )
    )
    db_session.commit()

    projected = get_legacy_job_projection_or_404(
        db_session,
        job_type="summarization",
        legacy_job_id="legacy-summary-1",
    )

    assert projected["id"] == "legacy-summary-1"
    assert projected["transcript_id"] == "transcript-9"
    assert projected["content_profile"] == "meeting"
    assert projected["status"] == "completed"
    assert projected["processing_time_seconds"] == 900.0
