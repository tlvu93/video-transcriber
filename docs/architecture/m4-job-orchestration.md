# M4 Job Orchestration and Realtime

This milestone completes the orchestration rebuild around a canonical PostgreSQL-backed job system.

## Outcomes

- `jobs` is now the canonical orchestration record for transcription, summarization, and translation work.
- `job_attempts` records each processing attempt, including expired and cancelled attempts.
- workers claim and heartbeat through the shared backend jobs domain instead of maintaining separate queue semantics.
- PostgreSQL `LISTEN/NOTIFY` wakes worker claim loops and backs cross-process live update fan-out.
- live UI updates are delivered over WebSockets, with SSE kept as a fallback transport.
- canonical jobs now support progress reporting, cancellation requests, and retry from the shared `/jobs` API.

## Compatibility

- legacy `/transcription-jobs`, `/summarization-jobs`, and `/translation-jobs` routes remain available as compatibility projections.
- legacy create, claim, heartbeat, list, get, complete, fail, and retry routes now project responses from canonical `jobs` rows instead of reading legacy job tables directly.
- `jobs.payload` is backfilled with legacy-only compatibility fields such as `video_id`, `transcript_id`, `content_profile`, `style_guide`, and `glossary_terms`.
- the frontend Jobs dashboard is now powered by the unified jobs API and exposes progress, cancel, retry, and attempt history.

## Scope Notes

- the orchestration system remains PostgreSQL-backed with timed polling as a fallback safety net.
- RabbitMQ is no longer part of the runtime topology.
- WebSocket delivery is shared-backplane safe; SSE remains available for browser compatibility and simpler debugging.
