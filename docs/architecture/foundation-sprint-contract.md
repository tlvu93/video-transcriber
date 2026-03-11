# Foundation Sprint Contract

This document is the backend contract for the 2026 foundation sprint. Other implementation branches should adapt to this contract instead of changing it.

## Supported Runtime Assumptions

- PostgreSQL is the supported multi-worker database runtime.
- SQLite remains a development-only fallback and is not supported for concurrent job leasing.
- REST plus SSE remains the application contract for this sprint.

## Job Leasing

All workers now claim jobs atomically through the API. RabbitMQ is only a wake-up signal and is not the source of job ownership.

### Lease Fields

The following additive fields are present on transcription, summarization, and translation job payloads:

- `worker_id: string | null`
- `lease_expires_at: string | null`

### Claim Endpoints

- `POST /transcription-jobs/claim`
- `POST /summarization-jobs/claim`
- `POST /translation-jobs/claim`

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

Workers are expected to heartbeat every 60 seconds while processing.

### Completion and Failure

Existing complete and fail endpoints remain in place, but now require `worker_id` in the request body and enforce lease ownership.

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

- `storage_path` is stored as the canonical absolute on-disk path for the video
- playback and processing use `storage_path` first
- recursive directory search remains fallback-only for legacy rows without `storage_path`

## Search Read Model

- Transcript JSON remains the source of truth.
- The API maintains a `transcript_segment_search` table for efficient `/search?q=` queries.
- Search response shape is unchanged.
