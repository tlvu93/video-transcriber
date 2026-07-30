from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

import backend.app.domain.jobs as jobs_module
from backend.app.api.job_views import get_legacy_job_projection_or_404
from backend.app.persistence.database import Base
from backend.app.persistence.models import JobAttempt, Transcript, UnifiedJob, Video


LEGACY_JOB_TABLES = {
    "transcription_jobs",
    "summarization_jobs",
    "translation_jobs",
}


def _build_session_factory(tmp_path: Path):
    database_url = f"sqlite:///{tmp_path / 'jobs.db'}"
    engine = sa.create_engine(database_url)
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _patch_job_runtime(monkeypatch, session_factory) -> None:
    monkeypatch.setattr(jobs_module, "SessionLocal", session_factory)
    monkeypatch.setattr(jobs_module, "publish_job_live_update_sync", lambda *args, **kwargs: None)
    monkeypatch.setattr(jobs_module, "record_metric_event", lambda *args, **kwargs: None)


def test_transcription_jobs_use_unified_rows_only(tmp_path, monkeypatch):
    engine, session_factory = _build_session_factory(tmp_path)
    _patch_job_runtime(monkeypatch, session_factory)

    with session_factory() as session:
        session.add(Video(id="video-1", filename="demo.mp4", status="pending"))
        session.commit()

    created_job = jobs_module.create_transcription_job_for_video("video-1")
    assert created_job["job_type"] == "transcription"
    assert created_job["video_id"] == "video-1"
    assert created_job["legacy_job_id"] == created_job["id"]

    claimed_job = jobs_module.claim_next_transcription_job("worker-1")
    assert claimed_job is not None
    assert claimed_job["id"] == created_job["id"]
    assert claimed_job["status"] == "processing"

    completed_job = jobs_module.complete_transcription_job(
        claimed_job["id"],
        "worker-1",
        processing_time=3.5,
    )
    assert completed_job["status"] == "completed"
    assert completed_job["processing_time_seconds"] == 3.5

    with session_factory() as session:
        stored_job = session.query(UnifiedJob).one()
        stored_attempt = session.query(JobAttempt).one()

        assert stored_job.legacy_job_table == "transcription_jobs"
        assert stored_job.legacy_job_id == stored_job.id
        assert stored_job.attempt_count == 1
        assert stored_attempt.status == "completed"
        assert stored_attempt.processing_time_seconds == 3.5

    assert LEGACY_JOB_TABLES.isdisjoint(sa.inspect(engine).get_table_names())


def test_translation_jobs_dedupe_active_requests_and_project_legacy_shape(tmp_path, monkeypatch):
    _engine, session_factory = _build_session_factory(tmp_path)
    _patch_job_runtime(monkeypatch, session_factory)

    with session_factory() as session:
        session.add(Video(id="video-2", filename="demo.mp4", status="completed"))
        session.add(
            Transcript(
                id="transcript-2",
                video_id="video-2",
                source_type="video",
                content="Hello world",
                format="txt",
                status="completed",
                language_code="en",
            )
        )
        session.commit()

    glossary_terms = [{"source_term": "AI", "target_term": "KI"}]
    created_job = jobs_module.create_translation_job_for_transcript(
        "transcript-2",
        "de",
        "en",
        style_guide="Use formal German",
        glossary_terms=glossary_terms,
    )
    duplicate_job = jobs_module.create_translation_job_for_transcript(
        "transcript-2",
        "de",
        "en",
        style_guide="Use formal German",
        glossary_terms=glossary_terms,
    )

    assert duplicate_job["id"] == created_job["id"]
    assert duplicate_job["legacy_job_id"] == created_job["legacy_job_id"]

    with session_factory() as session:
        stored_jobs = session.query(UnifiedJob).all()
        assert len(stored_jobs) == 1

        legacy_projection = get_legacy_job_projection_or_404(
            session,
            job_type="translation",
            legacy_job_id=created_job["legacy_job_id"],
        )

    assert legacy_projection["id"] == created_job["legacy_job_id"]
    assert legacy_projection["transcript_id"] == "transcript-2"
    assert legacy_projection["target_language"] == "de"
    assert legacy_projection["style_guide"] == "Use formal German"
    assert legacy_projection["glossary_terms"] == glossary_terms
