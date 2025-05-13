# Summarization Service

Service for summarizing transcripts in the Video Transcriber application.

## Overview

This service handles the summarization of transcripts:

- AI-powered summarization using Ollama
- Custom prompt engineering
- Job queue integration

## Installation

```bash
# Install the common package first
cd ../common
pip install -e .
cd ../summarization-service

# Install the summarization service
pip install -e .
```

## Usage

```bash
# Run the summarization service
python -m summarization.main

# Run with custom poll interval (in seconds)
python -m summarization.main --poll-interval 10
```

## How It Works

1. The service polls the database for new summarization jobs
2. When a job is found, it retrieves the transcript content
3. The transcript is summarized using an LLM (Ollama)
4. The summary is saved to a file and stored in the database
5. The job is marked as completed

## Environment Variables

- `LLM_HOST`: URL of the Ollama API (default: `http://localhost:11434/api/generate`)
- `LLM_MODEL`: Name of the model to use (default: `deepseek-r1`)

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black summarization
isort summarization

# Type checking
mypy summarization
```

## Docker

```bash
# Build the Docker image
docker build -t video-transcriber-summarization .

# Run the Docker container
docker run video-transcriber-summarization
```
