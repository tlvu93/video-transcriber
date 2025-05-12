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
- `watcher-service/`: Service for watching for new videos
