# Foundation Sprint Contract

This document is the backend contract for the 2026 foundation sprint. Other implementation branches should adapt to this contract instead of changing it.

## Supported Runtime Assumptions

- PostgreSQL is the only supported database runtime for the application and workers.
- `DATABASE_URL` must point to PostgreSQL. SQLite fallback behavior has been removed.
- The canonical backend runtime now uses shared backend domain services for orchestration instead of worker-to-API HTTP loops.
- Live updates are now delivered over WebSockets first, with SSE retained as a browser fallback.
- Realtime fan-out is backed by PostgreSQL `LISTEN/NOTIFY` so updates can cross API process boundaries.

## Job Leasing

All workers now claim jobs atomically through the shared backend orchestration layer and poll on a short interval with PostgreSQL notification wake-ups. PostgreSQL-backed leasing is the only source of job ownership.

### Lease Fields

The following additive fields are present on transcription, summarization, and translation job payloads:

- `worker_id: string | null`
- `lease_expires_at: string | null`

### Claim Endpoints

- `POST /transcription-jobs/claim`
- `POST /summarization-jobs/claim`
- `POST /translation-jobs/claim`

These compatibility routes now delegate to the canonical unified orchestration layer. The canonical backend runtimes use shared Python domain services directly instead of HTTP.

Request body:

```json
{
  "worker_id": "stable-worker-id"
}
```

Response:

- `200` with a claimed job payload when work is available
- `200` with `null` when no claimable job is available

Claim behavior:

- the API selects one `pending` job, or one `processing` job whose lease expired
- the API updates the job in the same transaction to:
  - `status = "processing"`
  - `worker_id = <request worker_id>`
  - `started_at = now()`
  - `lease_expires_at = now() + 10 minutes`
- legacy `GET .../next` and `POST .../{job_id}/start` worker routes have been removed

### Heartbeat Endpoints

- `POST /transcription-jobs/{job_id}/heartbeat`
- `POST /summarization-jobs/{job_id}/heartbeat`
- `POST /translation-jobs/{job_id}/heartbeat`

Request body:

```json
{
  "worker_id": "stable-worker-id"
}
```

Workers are expected to heartbeat every 60 seconds while processing. PostgreSQL `LISTEN/NOTIFY` is also used to wake claim loops immediately when relevant jobs change state.

### Completion and Failure

Existing complete and fail endpoints remain in place as compatibility routes, but now require `worker_id` in the request body and enforce unified lease ownership.

Example completion request:

```json
{
  "status": "completed",
  "worker_id": "stable-worker-id",
  "processing_time_seconds": 42.3
}
```

Example failure request:

```json
{
  "status": "failed",
  "worker_id": "stable-worker-id",
  "error_details": {
    "error": "message"
  }
}
```

Lease enforcement:

- `409 Conflict` is returned when the caller does not own the active lease
- successful completion or failure clears `worker_id` and `lease_expires_at`

### Cancellation and Retry

- `POST /jobs/{job_id}/cancel` requests cancellation for a canonical orchestration job
- `POST /jobs/{job_id}/retry` retries a failed or cancelled canonical orchestration job
- workers now checkpoint progress and cancellation between expensive phases
- active attempts are recorded in `job_attempts`, including cancelled and expired attempts

## Video Registration

`POST /videos/register` accepts an additive `storage_path` field.

Request example:

```json
{
  "filename": "meeting.mp4",
  "file_hash": "md5",
  "storage_path": "/absolute/path/to/meeting.mp4",
  "video_metadata": {
    "file_hash": "md5"
  }
}
```

Behavior:

- `storage_path` is the registration-time storage identity input and is normalized into `video_storage_objects`
- identity matching prefers `storage_path`, then `file_hash`
- filename-only matching remains fallback-only when neither `storage_path` nor `file_hash` is provided
- playback and processing use `storage_path` first
- recursive directory search fallback has been removed; path resolution now relies on canonical storage objects and configured storage roots

## Transcript Editing

- `speakers` persists canonical server-side speaker display names.
- `transcripts.review_status` and `transcripts.review_assignee` persist shared review state.
- `transcript_revisions` stores immutable edit snapshots for original transcripts.
- `transcript_comments` stores timestamp-linked review comments.
- `transcript_segments` and `translated_transcript_segments` are the canonical editable segment stores.
- `PUT /transcripts/{transcript_id}/speaker-aliases` updates persisted speaker aliases.
- `PATCH /transcripts/{transcript_id}/review` updates review status and assignee.
- `GET /transcripts/{transcript_id}/comments` lists review comments.
- `POST /transcripts/{transcript_id}/comments` creates a review comment.
- `DELETE /transcript-comments/{comment_id}` deletes a review comment.
- `GET /transcripts/{transcript_id}/revisions` lists revision snapshots in descending order.
- `POST /transcripts/{transcript_id}/revisions/{revision_id}/restore` restores an earlier snapshot and records a new restore revision.

## Translation Controls

- `POST /translation-jobs` accepts additive `style_guide` and `glossary_terms` fields for per-request localization control.
- `jobs.payload.style_guide` and `jobs.payload.glossary_terms` persist the requested translation context for compatibility routes and worker processing.
- `style_guides`, `glossary_terms`, and `translated_transcripts.qa_metrics` persist the applied localization context and subtitle QA readout.
- Subtitle QA currently records long-line, high-CPS, overlap, and missing-speaker warnings.

## Summary AI Controls

- `POST /summarization-jobs` accepts an additive `content_profile` field with `generic`, `meeting`, `podcast`, `lecture`, and `interview` as the supported values.
- `jobs.payload.content_profile` persists the requested profile when the user explicitly chooses one.
- `summaries.content_profile` stores the effective profile used for the completed output.
- `summaries.summary_metadata` stores structured AI enrichments, including headline, overview, key points, chapters, highlights, keywords, action items, named entities, open questions, and risks.
- `summary_variants` stores named rendered variants for the same summary output so downstream UI/export flows do not need to re-derive them from markdown.

## Search Read Model

- Transcript JSON remains the API compatibility payload.
- The backend now projects transcript and translated transcript segment payloads from normalized relational tables for editing and QA flows.
- The API maintains a `transcript_segment_search` table with PostgreSQL FTS and trigram indexes for `/search?q=` queries.
- `/search` now supports additive filters for `language_code`, `review_status`, `speaker`, `video_id`, and `video_title`.
- Search result items now also expose transcript `language_code` and `review_status`.

## Backend Exports

- `GET /transcripts/{transcript_id}/export` now generates backend `txt`, `srt`, `vtt`, `json`, `ass`, and `review_package` downloads.
- `GET /translated-transcripts/{translated_transcript_id}/export` now generates backend `txt`, `srt`, `vtt`, `json`, and `ass` downloads.
- `review_package` returns a zip archive containing transcript, revisions, comments, summaries, and translated variants.
- `txt` and `ass` exports honor `include_speakers`; `txt` also honors `include_timestamps`; `srt` and `vtt` exports use timeline segments only.

## Storage Backend

- `STORAGE_BACKEND=local_fs` is the current supported implementation.
- API path resolution and upload target allocation now flow through `api.storage`.
- `STORAGE_BACKEND=s3_compatible` now stores canonical `s3://bucket/key` URIs while resolving to a mounted local object-storage path for processing and watcher ingestion.
- The watcher is now optional and storage-backend aware; it only watches roots exposed by the active storage backend.

## Observability

- `/healthz` provides a lightweight readiness probe for API/database/storage state.
- `/metrics` aggregates persisted operational metrics over a configurable lookback window.
- request-scoped structured logging is the default runtime mode for API and workers.

## Collection Pagination

- Collection endpoints now return paginated envelopes with `items`, `total`, `limit`, and `offset`.
- `/videos/` also returns library-level stats so the frontend can page the grid without losing status totals.
- The primary collection endpoints support `limit` and `offset`, and `/videos/` additionally supports server-side filtering, sorting, and filename/title queries through `q`.
- The library page now persists the last-used filters/layout and supports named saved views for common review queues.
- Transcript exports now show explicit frontend download state while backend-generated assets are being prepared.

## Canonical Jobs API

- `jobs` and `job_attempts` are now the canonical orchestration write/read path.
- `GET /jobs` lists canonical jobs with shared filters for `job_type`, `status`, `subject_type`, and `subject_id`.
- `GET /jobs/{job_id}` returns one canonical job payload.
- `GET /jobs/{job_id}/attempts` returns execution attempts in reverse chronological order.
- compatibility transcription, summarization, and translation job endpoints now delegate into the canonical jobs domain before returning legacy-shaped payloads.
