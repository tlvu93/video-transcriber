# Video Transcriber Data Flow Diagram

```mermaid
graph TD
    %% Define nodes
    User[User]
    FileSystem[File System]
    Watcher[Watcher Service]
    API[API Service]
    TranscriptionWorker[Transcription Service]
    SummarizationWorker[Summarization Service]
    RabbitMQ[RabbitMQ]
    Postgres[(PostgreSQL DB)]
    Ollama[Ollama LLM]
    Frontend[Frontend]
    Whisper[Whisper Model]

    %% Define styles
    classDef service fill:#b8e0d2,stroke:#333,stroke-width:1px;
    classDef database fill:#d6eaf8,stroke:#333,stroke-width:1px;
    classDef messaging fill:#f9e79f,stroke:#333,stroke-width:1px;
    classDef model fill:#d7bde2,stroke:#333,stroke-width:1px;
    classDef frontend fill:#f5cba7,stroke:#333,stroke-width:1px;
    classDef storage fill:#d5dbdb,stroke:#333,stroke-width:1px;
    classDef user fill:#f5b7b1,stroke:#333,stroke-width:1px;

    %% Apply styles
    class Watcher,API,TranscriptionWorker,SummarizationWorker service;
    class Postgres database;
    class RabbitMQ messaging;
    class Whisper,Ollama model;
    class Frontend frontend;
    class FileSystem storage;
    class User user;

    %% Define relationships
    User -->|Uploads video| FileSystem
    User -->|Views results| Frontend

    %% Watcher Service Flow
    FileSystem -->|New video detected| Watcher
    Watcher -->|Register video| API
    Watcher -->|Publish video.created event| RabbitMQ

    %% API Service Flow
    API -->|Store video metadata| Postgres
    API -->|Create transcription job| Postgres
    API -->|Publish job.status.changed event| RabbitMQ

    %% Transcription Service Flow
    TranscriptionWorker -->|Get next job| API
    TranscriptionWorker -->|Read video file| FileSystem
    TranscriptionWorker -->|Use Whisper model| Whisper
    TranscriptionWorker -->|Store transcript| API
    TranscriptionWorker -->|Update job status| API
    TranscriptionWorker -->|Publish transcription.created event| RabbitMQ

    %% Summarization Service Flow
    SummarizationWorker -->|Get next job| API
    SummarizationWorker -->|Read transcript| Postgres
    SummarizationWorker -->|Use LLM for summarization| Ollama
    SummarizationWorker -->|Store summary| API
    SummarizationWorker -->|Update job status| API
    SummarizationWorker -->|Publish summary.created event| RabbitMQ

    %% Frontend Flow
    Frontend -->|Fetch video data| API
    Frontend -->|Fetch transcript data| API
    Frontend -->|Fetch summary data| API
    Frontend -->|Stream video| API

    %% Event Subscriptions
    RabbitMQ -->|video.created event| TranscriptionWorker
    RabbitMQ -->|job.status.changed event| TranscriptionWorker
    RabbitMQ -->|transcription.created event| SummarizationWorker
    RabbitMQ -->|job.status.changed event| SummarizationWorker
    RabbitMQ -->|job.status.changed event| API

    %% Database Relationships
    Postgres -->|Provide data| API
```

## Data Flow Description

1. **Video Ingestion**:

   - User uploads a video or places it in a monitored directory
   - Watcher Service detects the new video file
   - Watcher registers the video with the API Service
   - API Service stores video metadata in PostgreSQL
   - Watcher publishes a `video.created` event to RabbitMQ

2. **Transcription Process**:

   - API Service creates a transcription job in PostgreSQL
   - Transcription Service receives a `video.created` event from RabbitMQ
   - Transcription Service also listens for `job.status.changed` events
   - Transcription Service checks for pending jobs at startup (polling)
   - Transcription Service processes the video using Whisper model
   - Transcription Service stores the transcript via API
   - Transcription Service publishes a `transcription.created` event

3. **Summarization Process**:

   - API Service creates a summarization job
   - Summarization Service receives a `transcription.created` event from RabbitMQ
   - Summarization Service also listens for `job.status.changed` events
   - Summarization Service checks for pending jobs at startup (polling)
   - Summarization Service uses Ollama LLM to generate a summary
   - Summarization Service stores the summary via API
   - Summarization Service publishes a `summary.created` event

4. **Frontend Display**:
   - Frontend fetches video, transcript, and summary data from API
   - Frontend displays video with synchronized transcript
   - Frontend shows summary of the video content
   - User can interact with the video and transcript

This architecture uses a microservices approach with message-based communication through RabbitMQ, allowing for scalable and resilient processing of videos.

## Event-Driven vs. Polling Approaches

This system uses a combination of two approaches for service communication:

1. **Event-Driven (Push Model)**:

   - Services subscribe to specific events via RabbitMQ
   - When an event occurs, RabbitMQ pushes the notification to all subscribed services
   - Example: When a transcription is created, RabbitMQ notifies the Summarization Service
   - Advantages: Real-time processing, reduced latency, services only act when needed

2. **Polling (Pull Model)**:
   - Services periodically check the API for pending jobs
   - The service actively requests information rather than waiting for notifications
   - Example: Services check for pending jobs at startup to process any jobs that might have been missed
   - Advantages: Simpler implementation, works as a fallback mechanism

Using both approaches provides redundancy and ensures that no jobs are missed, even if a service was temporarily unavailable when an event was published.
