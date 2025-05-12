# Migration Plan: Monolithic to Microservice Architecture

This document outlines the plan for migrating the Video Transcriber application from a monolithic architecture to a microservice architecture.

## Overview

The current monolithic application will be split into the following microservices:

1. **Common Package**: Shared code and utilities used by all services
2. **API Service**: HTTP API for user interaction
3. **Transcription Service**: Service for transcribing videos
4. **Summarization Service**: Service for summarizing transcripts

## Migration Steps

### Phase 1: Setup Project Structure (Completed)

- [x] Create directory structure for microservices
- [x] Set up package configuration files (pyproject.toml)
- [x] Create Docker configuration files
- [x] Update docker-compose.yml

### Phase 2: Migrate Common Code

- [ ] Move database models to common package
- [ ] Move authentication code to common package
- [ ] Move job queue code to common package
- [ ] Move configuration settings to common package
- [ ] Move utility functions to common package
- [ ] Update imports in all services

### Phase 3: Migrate API Service

- [ ] Move API endpoints to api-service
- [ ] Update API routes and dependencies
- [ ] Test API endpoints

### Phase 4: Migrate Transcription Service

- [ ] Move transcription worker code to transcription-service
- [ ] Update transcription worker to use common package
- [ ] Test transcription functionality

### Phase 5: Migrate Summarization Service

- [ ] Move summarization worker code to summarization-service
- [ ] Update summarization worker to use common package
- [ ] Test summarization functionality

### Phase 6: Testing and Deployment

- [ ] Test all services individually
- [ ] Test integration between services
- [ ] Update deployment scripts
- [ ] Deploy to production

## File Migration Map

### Common Package

| Original File    | New Location               |
| ---------------- | -------------------------- |
| src/models.py    | common/common/models.py    |
| src/database.py  | common/common/database.py  |
| src/config.py    | common/common/config.py    |
| src/job_queue.py | common/common/job_queue.py |
| src/schemas.py   | common/common/schemas.py   |
| src/auth.py      | common/common/auth.py      |
| src/utils.py     | common/common/utils.py     |

### API Service

| Original File | New Location              |
| ------------- | ------------------------- |
| src/main.py   | api-service/api/main.py   |
| src/api.py    | api-service/api/routes.py |

### Transcription Service

| Original File               | New Location                                     |
| --------------------------- | ------------------------------------------------ |
| src/transcription_worker.py | transcription-service/transcription/worker.py    |
| src/processor.py            | transcription-service/transcription/processor.py |

### Summarization Service

| Original File               | New Location                                      |
| --------------------------- | ------------------------------------------------- |
| src/summarization_worker.py | summarization-service/summarization/worker.py     |
| src/summarizer.py           | summarization-service/summarization/summarizer.py |

## Database Migration

- Database schema remains the same
- All services connect to the same PostgreSQL database
- Database migrations are run from the API service

## Deployment Changes

- Each service has its own Dockerfile
- Services are deployed as separate containers
- Services communicate through the database and shared filesystem
- Frontend will be added later as a separate service

## Rollback Plan

In case of issues during migration:

1. Keep the original monolithic application running in parallel
2. Test each microservice thoroughly before switching
3. If issues arise, revert to the monolithic application
4. Address issues and retry migration

## Timeline

- Phase 1: 1 day
- Phase 2: 2 days
- Phase 3: 1 day
- Phase 4: 1 day
- Phase 5: 1 day
- Phase 6: 2 days

Total estimated time: 8 days
