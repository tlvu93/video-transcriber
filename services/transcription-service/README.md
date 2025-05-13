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
```

## How It Works

1. The service polls the database for new transcription jobs
2. When a job is found, it extracts the audio from the video file
3. The audio is transcribed using a speech recognition model
4. The transcript is saved to a file and stored in the database
5. The job is marked as completed

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
