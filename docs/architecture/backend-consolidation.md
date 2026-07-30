# Backend Consolidation

This document tracks the `M2 Backend Consolidation` milestone.

## Current State

The repo now has a canonical shared backend package at `backend/` with:

- `backend.app.entrypoints.api`
- `backend.app.entrypoints.transcription_worker`
- `backend.app.entrypoints.summarization_worker`
- `backend.app.entrypoints.translation_worker`
- `backend.app.entrypoints.watcher`

These entrypoints are now the preferred runtime surface for Docker Compose and Dockerfiles, and `backend/app` is the only Python source tree.

## What Changed

- Shared runtime bootstrapping now lives in `backend.app.runtime.bootstrap`.
- Shared backend domain services now live under `backend.app.domain.*`.
- Single-job polling worker behavior shared by summarization and translation now lives in `backend.app.runtime.single_job_worker`.
- The transcription worker runtime now also has a backend-native module at `backend.app.transcription.runner`.
- API, worker, watcher, and record modules now live under `backend.app.*` as the canonical implementation tree.
- Service folders now carry only Dockerfiles and runtime-specific lock files.
- Docker images now install the shared backend package with service-specific extras so consolidated entrypoints are available in every Python runtime container.
- Internal worker-to-API REST calls have been removed for local runtimes; workers now use shared backend services and PostgreSQL-backed domain operations directly.

## M2 Outcome

`M2 Backend Consolidation` is complete for the current roadmap scope:

- one canonical backend codebase under `backend/app`
- canonical runtime entrypoints under `backend.app.entrypoints.*`
- backend-native worker/runtime helpers
- container-specific Dockerfiles and lock files under `services/`
- no internal REST required between local backend runtimes

## Follow-On Work

Later milestones still build on top of this foundation, especially:

1. `M3` continuing the data-model shift from JSON-first records to normalized source-of-truth tables.
2. `M4` continuing to simplify orchestration now that the unified jobs view is the only persisted job system.
3. `M8` continuing to simplify runtime boundaries now that compatibility wrappers are gone.
