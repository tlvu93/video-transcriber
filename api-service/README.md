# API Service

HTTP API for the Video Transcriber application.

## Overview

This service provides the HTTP API for the Video Transcriber application:

- User authentication and authorization
- Video upload and management
- Transcript and summary retrieval
- Job status monitoring

## Installation

```bash
# Install the common package first
cd ../common
pip install -e .
cd ../api-service

# Install the API service
pip install -e .
```

## Usage

```bash
# Run the API service
python -m api.main
```

The API will be available at http://localhost:8000.

## API Endpoints

### Authentication

- `POST /auth/token`: Get an access token
- `POST /auth/register`: Register a new user (admin only)
- `GET /auth/me`: Get current user information

### Videos

- `POST /videos/upload`: Upload a new video
- `GET /videos`: List all videos
- `GET /videos/{video_id}`: Get video details
- `DELETE /videos/{video_id}`: Delete a video

### Transcripts

- `GET /transcripts`: List all transcripts
- `GET /transcripts/{transcript_id}`: Get transcript details
- `GET /transcripts/video/{video_id}`: Get transcript for a video

### Summaries

- `GET /summaries`: List all summaries
- `GET /summaries/{summary_id}`: Get summary details
- `GET /summaries/transcript/{transcript_id}`: Get summary for a transcript

### Jobs

- `GET /jobs`: List all jobs
- `GET /jobs/{job_id}`: Get job details
- `GET /jobs/status/{status}`: List jobs by status

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black api
isort api

# Type checking
mypy api
```

## Docker

```bash
# Build the Docker image
docker build -t video-transcriber-api .

# Run the Docker container
docker run -p 8000:8000 video-transcriber-api
```
