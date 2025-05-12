# Watcher Service

This service watches for new video files in the configured directory and triggers the processing pipeline when new files are detected.

## Features

- Monitors the video directory for new or modified video files
- Automatically triggers the processing pipeline when changes are detected
- Creates necessary directories on startup
- Runs an initial processing on startup to handle existing files

## Configuration

The service uses the common configuration module for settings such as:

- Video directory path
- Transcription directory path
- Summary directory path
- Database path

## Dependencies

- watchdog: For file system monitoring
- common: For configuration and database access
- api-service: For the main processing pipeline
