# Video Transcriber

A microservice-based application for transcribing and summarizing videos.

## Project Structure

The project is organized into several microservices:

- **common**: Shared code and utilities used by all services
- **api-service**: HTTP API for user interaction
- **transcription-service**: Service for transcribing videos
- **summarization-service**: Service for summarizing transcripts

## Services

### Common Package

Contains shared code and utilities used by all services:

- Database models and connection management
- Authentication and authorization
- Job queue management
- Configuration settings
- Utility functions

### API Service

Provides the HTTP API for the application:

- User authentication and authorization
- Video upload and management
- Transcript and summary retrieval
- Job status monitoring

### Transcription Service

Handles the transcription of video files:

- Automatic speech recognition
- Support for multiple video formats
- Job queue integration

### Summarization Service

Handles the summarization of transcripts:

- AI-powered summarization using Ollama
- Custom prompt engineering
- Job queue integration

## Setup and Installation

### Prerequisites

- Docker and Docker Compose
- PostgreSQL
- FFmpeg
- Python 3.9+

### Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/video-transcriber.git
cd video-transcriber
```

2. Install the common package:

```bash
cd common
pip install -e .
cd ..
```

3. Install each service:

```bash
cd api-service
pip install -e .
cd ../transcription-service
pip install -e .
cd ../summarization-service
pip install -e .
cd ..
```

## Running the Application

### Using Docker Compose

```bash
./run_docker.sh
```

### Running Services Individually

1. Start the API service:

```bash
cd api-service
python -m api.main
```

2. Start the Transcription service:

```bash
cd transcription-service
python -m transcription.main
```

3. Start the Summarization service:

```bash
cd summarization-service
python -m summarization.main
```

## Development

### Database Migrations

```bash
python run_migrations.py
```

### Running Tests

```bash
# TODO: Add test commands
```

## License

[MIT](LICENSE)
