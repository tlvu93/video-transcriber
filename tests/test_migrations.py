from __future__ import annotations

from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config

import backend.app.runtime.config as runtime_config
from alembic import command

ROOT_DIR = Path(__file__).resolve().parents[1]
LEGACY_JOB_TABLES = {
    "transcription_jobs",
    "summarization_jobs",
    "translation_jobs",
}
LEGACY_METADATA_COLUMNS = {
    "videos": {"storage_path"},
    "transcripts": {"speaker_aliases", "segments"},
    "translated_transcripts": {"segments", "style_guide", "glossary_terms"},
}


def _alembic_config(database_url: str) -> Config:
    config = Config(str(ROOT_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    runtime_config.DATABASE_URL = database_url
    return config


def _reflect_tables(engine: sa.Engine) -> dict[str, sa.Table]:
    metadata = sa.MetaData()
    metadata.reflect(bind=engine)
    return metadata.tables


def _column_names(table: sa.Table) -> set[str]:
    return {column.name for column in table.columns}


def _count_rows(connection: sa.Connection, table: sa.Table) -> int:
    return connection.execute(sa.select(sa.func.count()).select_from(table)).scalar_one()


def test_upgrade_from_pre_unified_schema_backfills_canonical_tables(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'pre_unified.db'}"
    alembic_config = _alembic_config(database_url)
    command.upgrade(alembic_config, "20260312_transcript_review_meta")

    engine = sa.create_engine(database_url)
    tables = _reflect_tables(engine)
    now = datetime(2026, 3, 15, 10, 0, 0)

    with engine.begin() as connection:
        connection.execute(
            tables["videos"].insert(),
            {
                "id": "video-1",
                "filename": "demo.mp4",
                "file_hash": "hash-1",
                "storage_path": "file:///data/demo.mp4",
                "status": "completed",
                "created_at": now,
                "video_metadata": {"source": "watcher"},
            },
        )
        connection.execute(
            tables["transcripts"].insert(),
            {
                "id": "transcript-1",
                "video_id": "video-1",
                "source_type": "video",
                "content": "Hello world\nHow are you",
                "format": "txt",
                "status": "completed",
                "language_code": "en",
                "speaker_aliases": {"SPEAKER_00": "Host"},
                "review_status": "draft",
                "review_assignee": None,
                "created_at": now,
                "segments": [
                    {
                        "id": 1,
                        "start_time": 0.0,
                        "end_time": 2.0,
                        "text": "Hello world",
                        "speaker": "SPEAKER_00",
                    },
                    {
                        "id": 2,
                        "start_time": 2.0,
                        "end_time": 4.0,
                        "text": "How are you",
                        "speaker": "SPEAKER_00",
                    },
                ],
            },
        )
        connection.execute(
            tables["summaries"].insert(),
            {
                "id": "summary-1",
                "transcript_id": "transcript-1",
                "content": "Short summary",
                "status": "completed",
                "created_at": now,
            },
        )
        connection.execute(
            tables["translated_transcripts"].insert(),
            {
                "id": "translation-1",
                "transcript_id": "transcript-1",
                "language": "fr",
                "content": "Bonjour le monde",
                "segments": [
                    {
                        "id": 1,
                        "start_time": 0.0,
                        "end_time": 2.0,
                        "text": "Bonjour le monde",
                        "speaker": "SPEAKER_00",
                    }
                ],
                "status": "completed",
                "created_at": now,
            },
        )
        connection.execute(
            tables["transcription_jobs"].insert(),
            {
                "id": "transcription-job-1",
                "video_id": "video-1",
                "status": "completed",
                "created_at": now,
                "started_at": now,
                "completed_at": now,
                "processing_time_seconds": 12.5,
                "error_details": None,
                "worker_id": "worker-a",
                "lease_expires_at": now,
            },
        )
        connection.execute(
            tables["summarization_jobs"].insert(),
            {
                "id": "summarization-job-1",
                "transcript_id": "transcript-1",
                "status": "pending",
                "created_at": now,
                "started_at": None,
                "completed_at": None,
                "processing_time_seconds": None,
                "error_details": None,
                "worker_id": None,
                "lease_expires_at": None,
            },
        )
        connection.execute(
            tables["translation_jobs"].insert(),
            {
                "id": "translation-job-1",
                "transcript_id": "transcript-1",
                "source_language": "en",
                "target_language": "fr",
                "status": "pending",
                "created_at": now,
                "started_at": None,
                "completed_at": None,
                "processing_time_seconds": None,
                "error_details": None,
                "worker_id": None,
                "lease_expires_at": None,
            },
        )

    command.upgrade(alembic_config, "head")

    tables = _reflect_tables(engine)
    assert LEGACY_JOB_TABLES.isdisjoint(tables)
    for table_name, legacy_columns in LEGACY_METADATA_COLUMNS.items():
        assert legacy_columns.isdisjoint(_column_names(tables[table_name]))
    with engine.connect() as connection:
        jobs = connection.execute(
            sa.select(
                tables["jobs"].c.legacy_job_id,
                tables["jobs"].c.job_type,
                tables["jobs"].c.payload,
                tables["jobs"].c.attempt_count,
            ).order_by(tables["jobs"].c.legacy_job_id)
        ).mappings().all()

        assert len(jobs) == 3
        payloads = {row["legacy_job_id"]: row["payload"] for row in jobs}
        assert payloads["transcription-job-1"]["video_id"] == "video-1"
        assert payloads["translation-job-1"]["transcript_id"] == "transcript-1"
        assert payloads["translation-job-1"]["target_language"] == "fr"
        assert payloads["translation-job-1"]["glossary_terms"] == []

        transcription_job = next(row for row in jobs if row["legacy_job_id"] == "transcription-job-1")
        assert transcription_job["attempt_count"] == 1

        storage_rows = _count_rows(connection, tables["video_storage_objects"])
        speaker_rows = _count_rows(connection, tables["speakers"])
        transcript_segment_rows = _count_rows(connection, tables["transcript_segments"])
        translated_segment_rows = _count_rows(connection, tables["translated_transcript_segments"])
        summary_variant_rows = _count_rows(connection, tables["summary_variants"])
        attempt_rows = _count_rows(connection, tables["job_attempts"])

        assert storage_rows == 1
        assert speaker_rows == 1
        assert transcript_segment_rows == 2
        assert translated_segment_rows == 1
        assert summary_variant_rows == 1
        assert attempt_rows == 1


def test_job_payload_backfill_migration_enriches_existing_unified_jobs(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'payload_backfill.db'}"
    alembic_config = _alembic_config(database_url)
    command.upgrade(alembic_config, "20260312_operational_metrics")

    engine = sa.create_engine(database_url)
    tables = _reflect_tables(engine)
    now = datetime(2026, 3, 15, 11, 0, 0)

    with engine.begin() as connection:
        connection.execute(
            tables["videos"].insert(),
            {
                "id": "video-2",
                "filename": "sync.mp4",
                "file_hash": "hash-2",
                "storage_path": "file:///data/sync.mp4",
                "status": "completed",
                "created_at": now,
                "video_metadata": {},
            },
        )
        connection.execute(
            tables["transcripts"].insert(),
            {
                "id": "transcript-2",
                "video_id": "video-2",
                "source_type": "video",
                "content": "Example",
                "format": "txt",
                "status": "completed",
                "language_code": "en",
                "speaker_aliases": {},
                "review_status": "draft",
                "review_assignee": None,
                "created_at": now,
                "segments": [{"id": 1, "start_time": 0.0, "end_time": 1.0, "text": "Example"}],
            },
        )
        connection.execute(
            tables["transcription_jobs"].insert(),
            {
                "id": "transcription-job-2",
                "video_id": "video-2",
                "status": "pending",
                "created_at": now,
                "started_at": None,
                "completed_at": None,
                "processing_time_seconds": None,
                "error_details": None,
                "worker_id": None,
                "lease_expires_at": None,
            },
        )
        connection.execute(
            tables["summarization_jobs"].insert(),
            {
                "id": "summarization-job-2",
                "transcript_id": "transcript-2",
                "content_profile": "meeting",
                "status": "pending",
                "created_at": now,
                "started_at": None,
                "completed_at": None,
                "processing_time_seconds": None,
                "error_details": None,
                "worker_id": None,
                "lease_expires_at": None,
            },
        )
        connection.execute(
            tables["translation_jobs"].insert(),
            {
                "id": "translation-job-2",
                "transcript_id": "transcript-2",
                "source_language": "en",
                "target_language": "de",
                "style_guide": "Use formal German",
                "glossary_terms": [{"source_term": "AI", "target_term": "KI"}],
                "status": "pending",
                "created_at": now,
                "started_at": None,
                "completed_at": None,
                "processing_time_seconds": None,
                "error_details": None,
                "worker_id": None,
                "lease_expires_at": None,
            },
        )
        connection.execute(
            tables["jobs"].insert(),
            [
                {
                    "id": "job-unified-1",
                    "legacy_job_table": "transcription_jobs",
                    "legacy_job_id": "transcription-job-2",
                    "job_type": "transcription",
                    "subject_type": "video",
                    "subject_id": "video-2",
                    "status": "pending",
                    "priority": 100,
                    "payload": {},
                    "progress": None,
                    "attempt_count": 0,
                    "worker_id": None,
                    "lease_expires_at": None,
                    "created_at": now,
                    "started_at": None,
                    "completed_at": None,
                    "processing_time_seconds": None,
                    "error_details": None,
                },
                {
                    "id": "job-unified-2",
                    "legacy_job_table": "summarization_jobs",
                    "legacy_job_id": "summarization-job-2",
                    "job_type": "summarization",
                    "subject_type": "transcript",
                    "subject_id": "transcript-2",
                    "status": "pending",
                    "priority": 100,
                    "payload": {},
                    "progress": None,
                    "attempt_count": 0,
                    "worker_id": None,
                    "lease_expires_at": None,
                    "created_at": now,
                    "started_at": None,
                    "completed_at": None,
                    "processing_time_seconds": None,
                    "error_details": None,
                },
                {
                    "id": "job-unified-3",
                    "legacy_job_table": "translation_jobs",
                    "legacy_job_id": "translation-job-2",
                    "job_type": "translation",
                    "subject_type": "transcript",
                    "subject_id": "transcript-2",
                    "status": "pending",
                    "priority": 100,
                    "payload": {"source_language": "en", "target_language": "de"},
                    "progress": None,
                    "attempt_count": 0,
                    "worker_id": None,
                    "lease_expires_at": None,
                    "created_at": now,
                    "started_at": None,
                    "completed_at": None,
                    "processing_time_seconds": None,
                    "error_details": None,
                },
            ],
        )

    command.upgrade(alembic_config, "head")

    tables = _reflect_tables(engine)
    assert LEGACY_JOB_TABLES.isdisjoint(tables)
    for table_name, legacy_columns in LEGACY_METADATA_COLUMNS.items():
        assert legacy_columns.isdisjoint(_column_names(tables[table_name]))
    with engine.connect() as connection:
        rows = connection.execute(
            sa.select(tables["jobs"].c.job_type, tables["jobs"].c.payload).order_by(tables["jobs"].c.job_type)
        ).mappings().all()

    payload_by_type = {row["job_type"]: row["payload"] for row in rows}
    assert payload_by_type["transcription"]["video_id"] == "video-2"
    assert payload_by_type["summarization"]["transcript_id"] == "transcript-2"
    assert payload_by_type["summarization"]["content_profile"] == "meeting"
    assert payload_by_type["translation"]["transcript_id"] == "transcript-2"
    assert payload_by_type["translation"]["style_guide"] == "Use formal German"
    assert payload_by_type["translation"]["glossary_terms"] == [
        {"source_term": "AI", "target_term": "KI"}
    ]


def test_cleanup_migration_downgrade_restores_legacy_job_tables(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'cleanup_downgrade.db'}"
    alembic_config = _alembic_config(database_url)
    command.upgrade(alembic_config, "head")

    engine = sa.create_engine(database_url)
    tables = _reflect_tables(engine)
    now = datetime(2026, 3, 15, 12, 0, 0)

    with engine.begin() as connection:
        connection.execute(
            tables["videos"].insert(),
            {
                "id": "video-3",
                "filename": "cleanup.mp4",
                "file_hash": "hash-3",
                "status": "completed",
                "created_at": now,
                "video_metadata": {},
            },
        )
        connection.execute(
            tables["video_storage_objects"].insert(),
            {
                "id": "storage-3",
                "video_id": "video-3",
                "storage_backend": "local_fs",
                "storage_uri": "file:///data/cleanup.mp4",
                "content_hash": "hash-3",
                "is_primary": True,
                "created_at": now,
                "updated_at": now,
            },
        )
        connection.execute(
            tables["transcripts"].insert(),
            {
                "id": "transcript-3",
                "video_id": "video-3",
                "source_type": "video",
                "content": "Cleanup transcript",
                "format": "txt",
                "status": "completed",
                "language_code": "en",
                "review_status": "draft",
                "review_assignee": None,
                "created_at": now,
            },
        )
        connection.execute(
            tables["transcript_segments"].insert(),
            {
                "transcript_id": "transcript-3",
                "segment_id": 1,
                "segment_index": 1,
                "start_time": 0.0,
                "end_time": 1.0,
                "text": "Cleanup transcript",
                "speaker": "SPEAKER_00",
                "created_at": now,
                "updated_at": now,
            },
        )
        connection.execute(
            tables["speakers"].insert(),
            {
                "id": "speaker-3",
                "transcript_id": "transcript-3",
                "speaker_key": "SPEAKER_00",
                "display_name": "Host",
                "created_at": now,
                "updated_at": now,
            },
        )
        connection.execute(
            tables["translated_transcripts"].insert(),
            {
                "id": "translated-3",
                "transcript_id": "transcript-3",
                "language": "de",
                "content": "Bereinigtes Transkript",
                "qa_metrics": {"quality": "good"},
                "status": "completed",
                "created_at": now,
            },
        )
        connection.execute(
            tables["translated_transcript_segments"].insert(),
            {
                "translated_transcript_id": "translated-3",
                "segment_id": 1,
                "segment_index": 1,
                "start_time": 0.0,
                "end_time": 1.0,
                "text": "Bereinigtes Transkript",
                "speaker": "SPEAKER_00",
                "created_at": now,
                "updated_at": now,
            },
        )
        connection.execute(
            tables["style_guides"].insert(),
            {
                "id": "style-guide-3",
                "translated_transcript_id": "translated-3",
                "content": "Formal",
                "created_at": now,
                "updated_at": now,
            },
        )
        connection.execute(
            tables["glossary_terms"].insert(),
            {
                "id": "glossary-3",
                "translated_transcript_id": "translated-3",
                "source_term": "AI",
                "target_term": "KI",
                "notes": None,
                "sort_order": 1,
                "created_at": now,
                "updated_at": now,
            },
        )
        connection.execute(
            tables["jobs"].insert(),
            [
                {
                    "id": "job-3a",
                    "legacy_job_table": "transcription_jobs",
                    "legacy_job_id": "legacy-transcription-3",
                    "job_type": "transcription",
                    "subject_type": "video",
                    "subject_id": "video-3",
                    "status": "completed",
                    "priority": 100,
                    "payload": {"video_id": "video-3"},
                    "progress": 1.0,
                    "attempt_count": 1,
                    "worker_id": None,
                    "lease_expires_at": None,
                    "created_at": now,
                    "started_at": now,
                    "completed_at": now,
                    "processing_time_seconds": 12.0,
                    "error_details": None,
                },
                {
                    "id": "job-3b",
                    "legacy_job_table": "summarization_jobs",
                    "legacy_job_id": "legacy-summary-3",
                    "job_type": "summarization",
                    "subject_type": "transcript",
                    "subject_id": "transcript-3",
                    "status": "pending",
                    "priority": 100,
                    "payload": {"transcript_id": "transcript-3", "content_profile": "meeting"},
                    "progress": 0.0,
                    "attempt_count": 0,
                    "worker_id": None,
                    "lease_expires_at": None,
                    "created_at": now,
                    "started_at": None,
                    "completed_at": None,
                    "processing_time_seconds": None,
                    "error_details": None,
                },
                {
                    "id": "job-3c",
                    "legacy_job_table": "translation_jobs",
                    "legacy_job_id": "legacy-translation-3",
                    "job_type": "translation",
                    "subject_type": "transcript",
                    "subject_id": "transcript-3",
                    "status": "pending",
                    "priority": 100,
                    "payload": {
                        "transcript_id": "transcript-3",
                        "source_language": "en",
                        "target_language": "de",
                        "style_guide": "Formal",
                        "glossary_terms": [{"source_term": "AI", "target_term": "KI"}],
                    },
                    "progress": 0.0,
                    "attempt_count": 0,
                    "worker_id": None,
                    "lease_expires_at": None,
                    "created_at": now,
                    "started_at": None,
                    "completed_at": None,
                    "processing_time_seconds": None,
                    "error_details": None,
                },
            ],
        )

    command.downgrade(alembic_config, "20260315_job_payload_backfill")

    tables = _reflect_tables(engine)
    assert LEGACY_JOB_TABLES.issubset(tables)
    for table_name, legacy_columns in LEGACY_METADATA_COLUMNS.items():
        assert legacy_columns.issubset(_column_names(tables[table_name]))

    with engine.connect() as connection:
        transcription_rows = connection.execute(sa.select(tables["transcription_jobs"])).mappings().all()
        summarization_rows = connection.execute(sa.select(tables["summarization_jobs"])).mappings().all()
        translation_rows = connection.execute(sa.select(tables["translation_jobs"])).mappings().all()
        restored_videos = connection.execute(sa.select(tables["videos"])).mappings().all()
        restored_transcripts = connection.execute(sa.select(tables["transcripts"])).mappings().all()
        restored_translations = connection.execute(sa.select(tables["translated_transcripts"])).mappings().all()

    assert transcription_rows[0]["id"] == "legacy-transcription-3"
    assert transcription_rows[0]["video_id"] == "video-3"
    assert summarization_rows[0]["content_profile"] == "meeting"
    assert translation_rows[0]["target_language"] == "de"
    assert translation_rows[0]["glossary_terms"] == [{"source_term": "AI", "target_term": "KI"}]
    assert restored_videos[0]["storage_path"] == "file:///data/cleanup.mp4"
    assert restored_transcripts[0]["speaker_aliases"] == {"SPEAKER_00": "Host"}
    assert restored_transcripts[0]["segments"] == [
        {
            "id": 1,
            "start_time": 0.0,
            "end_time": 1.0,
            "text": "Cleanup transcript",
            "speaker": "SPEAKER_00",
        }
    ]
    assert restored_translations[0]["style_guide"] == "Formal"
    assert restored_translations[0]["glossary_terms"] == [{"source_term": "AI", "target_term": "KI"}]
