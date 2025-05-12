# Video Transcriber

A service that transcribes videos, generates summaries, and provides an API for accessing the results.

## Project Structure

The project has been restructured into separate services:

- **api-service**: FastAPI-based API for accessing videos, transcripts, and summaries
- **common**: Shared code used by all services (database, models, config, etc.)
- **processor-service**: Processes videos to generate transcripts and summaries
- **summarization-service**: Generates summaries from transcripts
- **transcription-service**: Transcribes videos to text
- **watcher-service**: Watches for new videos and triggers processing

## Running the Application

You can run different components of the application using the `run.py` script:

```bash
# Run the API server
./run.py api

# Run the transcription worker
./run.py transcription

# Run the summarization worker
./run.py summarization

# Run the file watcher
./run.py watcher

# Process a specific video file
./run.py processor --file path/to/video.mp4
```

## Docker

You can also run the application using Docker:

```bash
# Build and run all services
docker-compose up -d

# Stop all services
docker-compose down
```

## Development

### Prerequisites

- Python 3.8+
- FFmpeg (for video processing)
- Ollama (for summarization)

### Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run the application: `./run.py api`

### Environment Variables

- `LLM_HOST`: URL of the Ollama API (default: http://localhost:11434/api/generate)
- `LLM_MODEL`: Name of the Ollama model to use (default: deepseek-r1)

## API Endpoints

- `GET /`: Root endpoint
- `POST /videos/`: Upload a video for transcription
- `GET /videos/`: List all videos
- `GET /videos/{video_id}`: Get a video by ID
- `GET /videos/{video_id}/download`: Download a video by ID
- `GET /transcripts/`: List all transcripts
- `GET /transcripts/{transcript_id}`: Get a transcript by ID
- `GET /summaries/`: List all summaries
- `GET /summaries/{summary_id}`: Get a summary by ID
