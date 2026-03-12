# M3 Data Model Redesign

This document records the `M3 Data Model Redesign and Migration` milestone.

## Outcome

The backend now maintains normalized relational tables for the main editable metadata that previously lived only in snapshot JSON/text fields:

- `video_storage_objects`
- `transcript_segments`
- `speakers`
- `transcript_revisions`
- `transcript_comments`
- `summary_variants`
- `translated_transcript_segments`
- `style_guides`
- `glossary_terms`
- `jobs`
- `job_attempts`

## Source Of Truth Rules

- `videos.storage_path` remains as a compatibility field, but canonical storage identity is also tracked in `video_storage_objects`.
- `transcripts.segments` and `translated_transcripts.segments` remain as compatibility snapshots, but writes now sync normalized segment rows first and then refresh the snapshot fields.
- `transcripts.speaker_aliases` remains as a compatibility snapshot, but speaker metadata is also stored in `speakers`.
- `translated_transcripts.style_guide` and `translated_transcripts.glossary_terms` remain as compatibility snapshots, but normalized rows live in `style_guides` and `glossary_terms`.
- `summaries.content` remains the primary summary text field, and `summary_variants` now stores the named/default variant row for future expansion.

## Migration Scope

The Alembic migration [20260312_normalized_metadata_tables.py](/Users/tuanvu/Projects/Own%20Apps/video-transcriber/alembic/versions/20260312_normalized_metadata_tables.py) backfills:

- storage objects from `videos.storage_path`
- speaker rows from `transcripts.speaker_aliases` plus segment speaker IDs
- summary variants from existing summaries
- style guides and glossary terms from translated transcript snapshot fields

## Runtime Behavior

The API and shared backend record services now keep these normalized tables updated during:

- uploads and watched-folder registration
- transcript creation
- transcript segment edits
- speaker alias edits
- transcript revision restores
- summary creation
- translated transcript creation and updates

This means the repo can keep its existing frontend/API contracts while the backend data model is now structured enough for later collaboration, storage abstraction, and richer QA workflows.
