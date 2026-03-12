# M8 Hardening, Cleanup, and Release Prep

This milestone closes the remaining operational and cleanup work after the architecture, schema, frontend, and AI milestones.

## Delivered

- API and worker runtime logging now uses a shared structured logging setup with request IDs
- persisted operational metric events now track API request volume/latency, queue wait time, worker processing time, cache-hit signals, export time, and search latency
- the API now exposes `/healthz` and `/metrics` for local operational checks
- recursive storage-path fallback scans have been removed in favor of canonical storage resolution only
- local backup and restore scripts now cover PostgreSQL plus app metadata/cache directories
- compose/runtime defaults now expose service names and structured logging settings instead of older transitional service-era assumptions

## Main Files

- `backend/app/runtime/observability.py`
- `backend/app/runtime/metrics.py`
- `backend/app/api/app.py`
- `backend/app/domain/jobs.py`
- `backend/app/transcription/transcription_worker.py`
- `backend/app/summarization/worker.py`
- `backend/app/translation/translation_worker.py`
- `backend/app/runtime/storage.py`
- `scripts/backup-local.sh`
- `scripts/restore-local.sh`

## Remaining Work After M8

The strict roadmap milestones are now complete. Any next step would be a new post-roadmap enhancement or stabilization pass rather than one of the original modernization milestones.
