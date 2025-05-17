# Video Transcriber Application Documentation

This document provides a comprehensive overview of the Video Transcriber application architecture, data flow, and component interactions.

## Table of Contents

1. [Application Overview](#application-overview)
2. [Application Flow](#application-flow)
3. [Data Flow](#data-flow)
4. [Architecture](#architecture)
5. [Key Components](#key-components)
6. [Data Models](#data-models)
7. [API Endpoints](#api-endpoints)

## Application Overview

The Video Transcriber is a microservices-based application that automatically transcribes and summarizes video content. It consists of several services that work together to process videos, generate transcripts, and create summaries.

### Key Features

- Automatic detection of new video files in a watched directory
- Video transcription using Whisper
- Transcript summarization using Ollama LLM
- Web interface for viewing videos, transcripts, and summaries
- Time-aligned transcript segments for navigating video content
- Job queue system for processing videos asynchronously

## Application Flow

The application flow is documented in detail in [video-transcriber-flow.md](video-transcriber-flow.md).

![Application Flow](video-transcriber-flow.md)

The flow consists of three main processes:

1. **Video Ingestion**:

   - User uploads a video through the frontend OR places a video file in the watched directory
   - The video file is stored in the file system
   - The video is registered in the database

2. **Transcription Process**:

   - The transcription service polls for pending transcription jobs
   - When a job is found, the service transcribes the video using Whisper
   - The transcript with time-aligned segments is created
   - A summarization job is created

3. **Summarization Process**:

   - The summarization service polls for pending summarization jobs
   - When a job is found, the service summarizes the transcript using Ollama LLM
   - The summary is stored in the database

4. **Frontend Display**:
   - The frontend fetches the video, transcript, and summary
   - The user can view the video, read the transcript, and see the summary
   - The user can click on transcript segments to navigate to specific parts of the video

## Data Flow

The data flow is documented in detail in [video-transcriber-data-flow.md](video-transcriber-data-flow.md).

![Data Flow](video-transcriber-data-flow.md)

The data flow diagram shows the sequence of API calls and data exchanges between the different services:

- How the watcher service registers videos and creates transcription jobs
- How the transcription service processes jobs and creates transcripts
- How the summarization service processes jobs and creates summaries
- How the frontend fetches and displays data

## Architecture

The architecture is documented in detail in [video-transcriber-architecture.md](video-transcriber-architecture.md).

![Architecture](video-transcriber-architecture.md)

The architecture diagram shows the deployment of the application using Docker Compose:

- The containerized services and their relationships
- The data storage components
- The external interfaces
- The data flow through the system

## Key Components

### Services

- **Watcher Service**: Monitors a directory for new video files
- **API Service**: Provides REST API endpoints for all operations
- **Transcription Service**: Transcribes videos using Whisper
- **Summarization Service**: Summarizes transcripts using Ollama LLM
- **Frontend**: React application for user interaction

### Data Storage

- **PostgreSQL Database**: Stores metadata, transcripts, and summaries
- **File System**: Stores video files

### External Dependencies

- **Whisper**: AI model for speech-to-text transcription
- **Ollama LLM**: Local large language model for generating summaries

## Data Models

The application uses several data models to represent the different entities in the system:

### Video

- `id`: Unique identifier
- `filename`: Name of the video file
- `status`: Current status (pending, transcribed, error)
- `created_at`: Timestamp when the video was added
- `file_hash`: Hash of the video file for deduplication
- `video_metadata`: Additional metadata about the video

### Transcript

- `id`: Unique identifier
- `video_id`: Reference to the video
- `source_type`: Type of source (video)
- `content`: Full transcript text
- `format`: Format of the transcript (txt, srt)
- `status`: Current status (completed, summarized, error)
- `created_at`: Timestamp when the transcript was created
- `segments`: Time-aligned segments of the transcript

### Summary

- `id`: Unique identifier
- `transcript_id`: Reference to the transcript
- `content`: Summary text
- `status`: Current status (completed, error)
- `created_at`: Timestamp when the summary was created

### TranscriptionJob

- `id`: Unique identifier
- `video_id`: Reference to the video
- `status`: Current status (pending, in_progress, completed, failed)
- `created_at`: Timestamp when the job was created
- `started_at`: Timestamp when the job was started
- `completed_at`: Timestamp when the job was completed
- `processing_time_seconds`: Time taken to process the job
- `error_details`: Details of any errors that occurred

### SummarizationJob

- `id`: Unique identifier
- `transcript_id`: Reference to the transcript
- `status`: Current status (pending, in_progress, completed, failed)
- `created_at`: Timestamp when the job was created
- `started_at`: Timestamp when the job was started
- `completed_at`: Timestamp when the job was completed
- `processing_time_seconds`: Time taken to process the job
- `error_details`: Details of any errors that occurred

## API Endpoints

The API service provides several endpoints for interacting with the application:

### Video Endpoints

- `GET /videos/`: List all videos
- `GET /videos/{id}`: Get a video by ID
- `POST /videos/`: Upload a new video
- `POST /videos/register`: Register an existing video file
- `POST /videos/check`: Check if a video exists
- `PATCH /videos/{id}`: Update a video
- `GET /videos/{id}/download`: Download a video

### Transcript Endpoints

- `GET /transcripts/`: List all transcripts
- `GET /transcripts/{id}`: Get a transcript by ID
- `POST /transcripts/`: Create a new transcript
- `PATCH /transcripts/{id}`: Update a transcript

### Summary Endpoints

- `GET /summaries/`: List all summaries
- `GET /summaries/{id}`: Get a summary by ID
- `POST /summaries/`: Create a new summary

### Transcription Job Endpoints

- `POST /transcription-jobs/`: Create a new transcription job
- `GET /transcription-jobs/next`: Get the next pending transcription job
- `GET /transcription-jobs/{id}`: Get a transcription job by ID
- `POST /transcription-jobs/{id}/start`: Mark a transcription job as started
- `POST /transcription-jobs/{id}/complete`: Mark a transcription job as completed
- `POST /transcription-jobs/{id}/fail`: Mark a transcription job as failed
- `POST /transcription-jobs/{id}/retry`: Retry a failed transcription job

### Summarization Job Endpoints

- `POST /summarization-jobs/`: Create a new summarization job
- `GET /summarization-jobs/next`: Get the next pending summarization job
- `GET /summarization-jobs/{id}`: Get a summarization job by ID
- `POST /summarization-jobs/{id}/start`: Mark a summarization job as started
- `POST /summarization-jobs/{id}/complete`: Mark a summarization job as completed
- `POST /summarization-jobs/{id}/fail`: Mark a summarization job as failed
