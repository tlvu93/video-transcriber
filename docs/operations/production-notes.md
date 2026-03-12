# Production Notes

## PostgreSQL Upgrade

The modernization baseline now targets PostgreSQL 18.3.

If you are carrying forward data from an older local stack, use logical dump and restore rather than in-place upgrades.

Recommended sequence:

1. Stop writers.
2. Run `pg_dump` against the source PostgreSQL database.
3. Restore into a clean PostgreSQL 18.3 instance with `pg_restore` or `psql`.
4. Start the upgraded stack and let Alembic apply application schema changes.

## Queue Leasing

- PostgreSQL is the only supported runtime for leased job processing.
- Workers must claim work through the `/claim` endpoints and maintain ownership via heartbeat.
- RabbitMQ has been removed from the runtime topology; workers poll the API for claimable jobs.
- Canonical `/jobs` and `/jobs/{job_id}/attempts` endpoints are now available for cross-job operational visibility.

## Live Updates

- SSE remains the browser-facing contract.
- Event fan-out now uses PostgreSQL `LISTEN/NOTIFY` as a shared backplane, so updates can propagate across multiple API processes.
- `LIVE_UPDATES_NOTIFY_ENABLED=1` keeps the backplane active by default.
- `LIVE_UPDATES_CHANNEL` must stay consistent across API instances pointing at the same PostgreSQL database.

## AI Workers

- Summarization and translation now talk to Ollama directly over HTTP without LangChain wrappers.
- Summaries use content-profile-aware prompts instead of a meeting-only template.
- Translation jobs now accept optional style-guide text and glossary terms, and translated transcripts persist subtitle QA metrics for operator review.

## Storage Backend

- `STORAGE_BACKEND=local_fs` is the active mode.
- `s3_compatible` now maps canonical `s3://bucket/key` URIs onto a mounted local object-storage path for worker processing.
- Recursive on-disk fallback scans have been removed; workers and playback now rely on canonical storage URIs plus configured storage roots.

## Observability

- API and worker logging now use a shared structured logger with service names and request IDs.
- `/healthz` checks API/database readiness and reports the active storage backend.
- `/metrics` aggregates persisted local operational metrics such as request latency, queue wait time, worker processing time, search latency, export time, and translation cache-hit signals.

## Backup and Restore

- `./scripts/backup-local.sh` creates a PostgreSQL dump plus an app metadata archive.
- `./scripts/restore-local.sh <backup-dir>` restores both the database dump and the metadata archive.
- Video files are intentionally excluded from these backups; keep media assets in their original storage backend or watched paths.
