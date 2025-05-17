# Video Transcriber Data Flow

```mermaid
sequenceDiagram
    participant User
    participant Watcher as Watcher Service
    participant API as API Service
    participant DB as PostgreSQL Database
    participant FS as File System
    participant TS as Transcription Service
    participant SS as Summarization Service
    participant LLM as Ollama LLM
    participant FE as Frontend

    %% Video Upload Flow
    alt Video Upload via Frontend
        User->>FE: Upload video
        FE->>API: POST /videos/
        API->>FS: Save video file
        API->>DB: Create video record
        API->>DB: Create transcription job
        API-->>FE: Return video details
    else Video Placed in Watched Directory
        User->>FS: Place video in watched directory
        Watcher->>FS: Detect new video
        Watcher->>API: POST /videos/check
        API->>DB: Check if video exists
        API-->>Watcher: Return result

        alt Video Does Not Exist
            Watcher->>API: POST /videos/register
            API->>DB: Create video record
            API-->>Watcher: Return video details

            Watcher->>API: POST /transcription-jobs/
            API->>DB: Create transcription job
            API-->>Watcher: Return job details
        end
    end

    %% Transcription Flow
    loop Poll for Transcription Jobs
        TS->>API: GET /transcription-jobs/next
        API->>DB: Query for pending jobs
        API-->>TS: Return next job (if any)

        alt Job Available
            TS->>API: POST /transcription-jobs/{id}/start
            API->>DB: Mark job as started
            API-->>TS: Return updated job

            TS->>FS: Load video file
            TS->>TS: Transcribe with Whisper

            TS->>API: POST /transcripts/
            API->>DB: Create transcript record
            API-->>TS: Return transcript details

            TS->>API: PATCH /videos/{id}
            API->>DB: Update video status to "transcribed"
            API-->>TS: Return updated video

            TS->>API: POST /summarization-jobs/
            API->>DB: Create summarization job
            API-->>TS: Return job details

            TS->>API: POST /transcription-jobs/{id}/complete
            API->>DB: Mark job as completed
            API-->>TS: Return updated job
        end
    end

    %% Summarization Flow
    loop Poll for Summarization Jobs
        SS->>API: GET /summarization-jobs/next
        API->>DB: Query for pending jobs
        API-->>SS: Return next job (if any)

        alt Job Available
            SS->>API: POST /summarization-jobs/{id}/start
            API->>DB: Mark job as started
            API-->>SS: Return updated job

            SS->>API: GET /transcripts/{id}
            API->>DB: Query for transcript
            API-->>SS: Return transcript

            SS->>LLM: Send transcript for summarization
            LLM-->>SS: Return summary

            SS->>API: POST /summaries/
            API->>DB: Create summary record
            API-->>SS: Return summary details

            SS->>API: PATCH /transcripts/{id}
            API->>DB: Update transcript status to "summarized"
            API-->>SS: Return updated transcript

            SS->>API: POST /summarization-jobs/{id}/complete
            API->>DB: Mark job as completed
            API-->>SS: Return updated job
        end
    end

    %% Frontend Display Flow
    User->>FE: Navigate to video detail page
    FE->>API: GET /videos/{id}
    API->>DB: Query for video
    API-->>FE: Return video details

    FE->>API: GET /transcripts/?video_id={id}
    API->>DB: Query for transcripts
    API-->>FE: Return transcripts

    FE->>API: GET /summaries/?transcript_id={id}
    API->>DB: Query for summaries
    API-->>FE: Return summaries

    FE->>API: GET /videos/{id}/download
    API->>FS: Get video file
    API-->>FE: Return video file

    FE->>User: Display video, transcript, and summary
```

## Data Models

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
