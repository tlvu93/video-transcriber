# Video Transcriber

A service for transcribing and summarizing videos using AI.

## Quick Start

The easiest way to use the application is through the CLI:

```bash
# Initialize the project
./vt init

# Start Docker services
./vt docker start

# Check status
./vt docker status

# Create an admin user
./vt user create-admin

# Run database migrations
./vt db migrate

# View logs
./vt docker logs
```

## CLI Documentation

The Video Transcriber CLI provides a unified interface for managing the application. For detailed documentation, see:

- [Quick Start Guide](vt-cli/README-SCRIPTS.md)
- [Detailed Documentation](vt-cli/SCRIPTS.md)

## Getting Help

All scripts provide help information when run with the `-h` or `--help` flag:

```bash
./vt help
./vt docker -h
./vt db -h
```

## Project Structure

- `api-service/`: API service for the application
- `common/`: Common code shared between services
- `data/`: Data directories for videos, transcriptions, and summaries
- `migrations/`: Database migration scripts
- `summarization-service/`: Service for summarizing transcriptions
- `transcription-service/`: Service for transcribing videos
- `vt-cli/`: CLI tools for managing the application

## Configuration

### Transcription Service Queue

The transcription service now includes a queue system to handle multiple transcription requests efficiently. This prevents the service from being overwhelmed when many requests come in simultaneously.

You can configure the queue with the following environment variables:

- `MAX_WORKERS`: Maximum number of worker threads to process transcription jobs concurrently (default: 2)
- `POLL_INTERVAL`: Interval in seconds between polling for new jobs (default: 5)

Example:

```bash
# Start with 4 worker threads
MAX_WORKERS=4 ./vt docker start

# Or set environment variables before starting
export MAX_WORKERS=4
export POLL_INTERVAL=10
./vt docker start
```

You can also modify these values directly in the `docker-compose.yml` file.

### Video Watcher Service

The watcher service monitors video directories for new video files and automatically processes them.

#### Nested Folders Support

The watcher service now supports detecting videos in nested folders. Any video files placed in subdirectories of the configured video directories will be automatically detected and processed.

#### Multiple Video Directories

You can configure multiple video directories to be watched by setting the `VIDEO_DIRS` environment variable. Separate multiple directories with commas.

Example:

```bash
# Watch multiple directories
VIDEO_DIRS=/app/data/videos,/app/data/external_videos ./vt docker start

# Or set environment variables before starting
export VIDEO_DIRS=/app/data/videos,/app/data/external_videos
./vt docker start
```

By default, the watcher service monitors the `/app/data/videos` directory inside the container (which maps to `./data/videos` on your host machine).
