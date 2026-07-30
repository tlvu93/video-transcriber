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

- `video_storage_objects` is the canonical storage identity for each video.
- `transcript_segments` and `translated_transcript_segments` are the canonical editable segment stores.
- `speakers` is the canonical transcript speaker-alias store.
- `style_guides` and `glossary_terms` are the canonical localization-metadata stores for translated transcripts.
- `summaries.content` remains the primary summary text field, and `summary_variants` now stores the named/default variant row for future expansion.

## Migration Scope

The Alembic migration [20260312_normalized_metadata_tables.py](/Users/tuanvu/Projects/Own%20Apps/video-transcriber/alembic/versions/20260312_normalized_metadata_tables.py) backfills:

- storage objects from legacy video storage paths
- speaker rows from legacy transcript speaker aliases plus segment speaker IDs
- summary variants from existing summaries
- style guides and glossary terms from legacy translated transcript localization fields

## Runtime Behavior

The API and shared backend record services now keep these normalized tables updated during:

- uploads and watched-folder registration
- transcript creation
- transcript segment edits
- speaker alias edits
- transcript revision restores
- summary creation
- translated transcript creation and updates

This means the repo can keep its existing frontend/API contracts while the backend data model is structured enough for later collaboration, storage abstraction, and richer QA workflows.

## Current Write Strategy

- normalized segment, speaker, glossary, and search rows are updated incrementally rather than being fully deleted and reinserted on every edit
- the legacy snapshot columns have been removed; compatibility payloads are now projected directly from canonical normalized rows
- legacy job endpoints now read from canonical `jobs` rows and project legacy response shapes from `jobs.payload` rather than querying legacy job tables for reads
