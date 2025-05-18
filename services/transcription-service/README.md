# Transcription Service

Service for transcribing videos in the Video Transcriber application.

## Overview

This service handles the transcription of video files:

- Automatic speech recognition
- Support for multiple video formats
- Job queue integration

## Installation

```bash
# Install the common package first
cd ../common
pip install -e .
cd ../transcription-service

# Install the transcription service
pip install -e .
```

## Usage

```bash
# Run the transcription service
python -m transcription.main

# Run with custom poll interval (in seconds)
python -m transcription.main --poll-interval 10

# Run with multiple worker threads
python -m transcription.main --max-workers 4

# Run with both custom poll interval and multiple workers
python -m transcription.main --poll-interval 10 --max-workers 4
```

## How It Works

1. The service polls the database for new transcription jobs
2. Jobs are added to a queue and processed by worker threads
3. Each worker extracts the audio from the video file
4. The audio is transcribed using a speech recognition model
5. The transcript is saved to a file and stored in the database
6. The job is marked as completed

## Queue System

The service now includes a queue system to handle multiple transcription requests efficiently. This prevents the service from being overwhelmed when many requests come in simultaneously.

### Configuration

You can configure the queue with the following command-line arguments:

- `--max-workers`: Maximum number of worker threads to process transcription jobs concurrently (default: 1)
- `--poll-interval`: Interval in seconds between polling for new jobs (default: 5)

When running with Docker, you can set these values using environment variables:

- `MAX_WORKERS`: Same as `--max-workers`
- `POLL_INTERVAL`: Same as `--poll-interval`

### How the Queue Works

1. The queue manager runs in a separate thread and polls for new jobs
2. When a job is found, it's added to the queue
3. Worker threads pick up jobs from the queue and process them
4. The number of concurrent jobs is limited by the `max-workers` setting
5. If all workers are busy, new jobs wait in the queue until a worker becomes available

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black transcription
isort transcription

# Type checking
mypy transcription
```

## Docker

```bash
# Build the Docker image
docker build -t video-transcriber-transcription .

# Run the Docker container
docker run video-transcriber-transcription
```
