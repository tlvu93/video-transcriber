# Video Transcriber Application Flow

```mermaid
graph TD
    subgraph "Data Storage"
        DB[(PostgreSQL Database)]
        FS[File System]
    end

    subgraph "Backend Services"
        WS[Watcher Service]
        API[API Service]
        TS[Transcription Service]
        SS[Summarization Service]
        OLLAMA[Ollama LLM]
    end

    subgraph "Frontend"
        FE[React Frontend]
        VP[Video Player]
        TL[Transcript List]
        VS[Video Summary]
    end

    %% Watcher Service Flow
    WS -->|Monitors| FS
    WS -->|Registers video & creates transcription job| API

    %% Transcription Service Flow
    TS -->|Polls for pending jobs| API
    API -->|Returns transcription job| TS
    TS -->|Transcribes video using Whisper| FS
    TS -->|Creates transcript & summarization job| API

    %% Summarization Service Flow
    SS -->|Polls for pending jobs| API
    API -->|Returns summarization job| SS
    SS -->|Fetches transcript| API
    SS -->|Generates summary using LLM| OLLAMA
    SS -->|Saves summary| API

    %% Frontend Flow
    FE -->|Fetches video, transcript & summary| API
    FE -->|Displays video| VP
    FE -->|Displays transcript| TL
    FE -->|Displays summary| VS

    %% Database Interactions
    API <-->|Stores/retrieves data| DB

    %% File System Interactions
    FS -->|Video files| TS

    %% User Interactions
    User((User)) -->|Uploads video| FE
    User -->|Views video, transcript & summary| FE
    User -->|Places video in watched folder| FS
```

## Detailed Process Flow

1. **Video Ingestion**:

   - User uploads a video through the frontend OR places a video file in the watched directory
   - The video file is stored in the file system
   - The video is registered in the database

2. **Transcription Process**:

   - The transcription service polls for pending transcription jobs
   - When a job is found, the service:
     - Loads the Whisper model
     - Transcribes the video
     - Creates a transcript with time-aligned segments
     - Updates the video status to "transcribed"
     - Creates a summarization job

3. **Summarization Process**:

   - The summarization service polls for pending summarization jobs
   - When a job is found, the service:
     - Fetches the transcript
     - Sends the transcript to the Ollama LLM for summarization
     - Saves the summary
     - Updates the transcript status to "summarized"

4. **Frontend Display**:
   - The frontend fetches the video, transcript, and summary
   - Displays the video with a player
   - Shows the transcript with time-aligned segments
   - Displays the summary
   - Allows the user to click on transcript segments to seek to that point in the video

## Components

### Services

- **Watcher Service**: Monitors a directory for new video files
- **API Service**: Provides REST API endpoints for all operations
- **Transcription Service**: Transcribes videos using Whisper
- **Summarization Service**: Summarizes transcripts using Ollama LLM

### Data Storage

- **PostgreSQL Database**: Stores metadata, transcripts, and summaries
- **File System**: Stores video files

### Frontend

- **React Frontend**: User interface for the application
- **Video Player**: Displays the video
- **Transcript List**: Shows the transcript with time-aligned segments
- **Video Summary**: Displays the summary of the video content
