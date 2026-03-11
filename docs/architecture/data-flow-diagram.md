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
    TranscriptionWorker -->|Claim leased job| API
    TranscriptionWorker -->|Read video file| FileSystem
    TranscriptionWorker -->|Use Whisper model| Whisper
    TranscriptionWorker -->|Store transcript| API
    TranscriptionWorker -->|Update job status| API
    TranscriptionWorker -->|Publish transcription.created event| RabbitMQ

    %% Summarization Service Flow
    SummarizationWorker -->|Claim leased job| API
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
   - Transcription Service receives wake-up events from RabbitMQ
   - Transcription Service claims jobs through the API leasing endpoints
   - Transcription Service heartbeats while processing long-running work
   - Transcription Service processes the video using Whisper model
   - Transcription Service stores the transcript via API
   - Transcription Service publishes a `transcription.created` event

3. **Summarization Process**:

   - API Service creates a summarization job
   - Summarization Service receives wake-up events from RabbitMQ
   - Summarization Service claims jobs through the API leasing endpoints
   - Summarization Service heartbeats while processing long-running work
   - Summarization Service uses Ollama LLM to generate a summary
   - Summarization Service stores the summary via API
   - Summarization Service publishes a `summary.created` event

4. **Frontend Display**:
   - Frontend fetches video, transcript, and summary data from API
   - Frontend displays video with synchronized transcript
   - Frontend shows summary of the video content
   - User can interact with the video and transcript

This architecture uses a microservices approach with message-based communication through RabbitMQ, allowing for scalable and resilient processing of videos.

## Event-Driven Wake-Ups and API Leasing

This system uses a combination of two approaches for service communication:

1. **Event-Driven Wake-Ups**:

   - Services subscribe to relevant events via RabbitMQ
   - RabbitMQ acts as a wake-up signal so workers know when to attempt another claim
   - Example: When a transcription is created, RabbitMQ notifies the Summarization Service
   - Advantages: low latency and less idle polling

2. **API Job Leasing**:
   - Workers atomically claim jobs through the API and extend ownership with heartbeats
   - PostgreSQL-backed leases prevent multiple workers from processing the same job
   - Workers can still claim on startup or on a timed fallback when no wake-up event is received
   - Advantages: race-safe ownership with predictable recovery from stalled workers

Using both approaches provides low-latency wake-ups without making RabbitMQ the source of truth for job ownership.
