# Video Transcriber

A modular system for transcribing videos and generating summaries with analytics tracking.

## Known Issues and Fixes

### Database Initialization Issue

There is a known issue with the initialization script (`init.sh`) where the "videos" table is created twice, resulting in a "DuplicateTable" error. This happens because:

1. The Alembic migration creates the tables
2. The application's `init_db()` function also tries to create the tables

To fix this issue, we've provided a fix_database.sh script that:

1. Sets the SKIP_DB_INIT environment variable to prevent duplicate table creation
2. Runs the migrations properly to create all tables
3. Restarts the services with the correct configuration

To apply the fix, run:

```bash
./fix_database.sh
```

For new installations, the updated `init.sh` script already includes this fix.

## Architecture

The Video Transcriber is built with a modular architecture that separates the transcription and summarization processes:

- **API Layer**: FastAPI for handling HTTP requests
- **Database**: PostgreSQL for storing videos, transcripts, summaries, and processing metrics
- **Workers**: Separate worker processes for transcription and summarization
- **Analytics**: Built-in tracking of processing metrics

## Features

- Upload videos for transcription and summarization
- Enter transcripts manually for summarization
- Track processing metrics (time, success rate, etc.)
- View analytics on processing performance
- Reprocess videos or transcripts as needed

## Components

### Backend

- **API Layer**: FastAPI (Python)
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **File Storage**: File system for video/transcript/summary storage
- **Processing**: Whisper for transcription, Ollama for summarization
- **Analytics**: Built-in metrics tracking

## Setup

### Prerequisites

- Docker and Docker Compose
- FFmpeg (for video processing)
- Ollama (for summarization)

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/video-transcriber.git
   cd video-transcriber
   ```

2. Initialize the project with a single command:

   ```bash
   ./init.sh
   ```

   This will:

   - Create necessary directories
   - Build and start the Docker services
   - Run database migrations
   - Create an admin user
   - Check the status of all services

   You can customize the admin credentials:

   ```bash
   ./init.sh -u superadmin -p mysecretpassword
   ```

3. Access the API at http://localhost:8000

#### Manual Installation

If you prefer to install step by step:

1. Build and start the services:

   ```bash
   ./run_docker.sh
   ```

2. Run database migrations:

   ```bash
   ./run_migrations_docker.sh
   ```

3. Create an admin user:

   ```bash
   ./create_admin.sh
   ```

### Running Locally

You can also run the application locally without Docker:

1. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Make sure PostgreSQL and Ollama are running locally

3. Run the application:

   ```bash
   ./run_local.sh
   ```

### Helper Scripts

The project includes several helper scripts:

- `init.sh` - Initialize the project (use `./init.sh -h` for help)
- `run_docker.sh` - Build and start the services in Docker
- `stop_docker.sh` - Stop the Docker services
- `restart.sh` - Restart Docker services (use `./restart.sh -h` for help)
- `update.sh` - Update Docker images and rebuild services (use `./update.sh -h` for help)
- `run_migrations_docker.sh` - Run database migrations in Docker
- `run_local.sh` - Run the application locally
- `run_migrations.py` - Run database migrations locally
- `view_logs.sh` - View logs of Docker services (use `./view_logs.sh -h` for help)
- `check_status.sh` - Check the status of Docker services
- `db_status.sh` - Show the status of the database
- `create_user.sh` - Create a new user in the database (use `./create_user.sh -h` for help)
- `create_admin.sh` - Create an initial admin user (use `./create_admin.sh -h` for help)
- `cleanup.sh` - Clean up the Docker environment (use `./cleanup.sh -h` for help)
- `backup.sh` - Create a backup of the database (use `./backup.sh -h` for help)
- `restore.sh` - Restore a database backup (use `./restore.sh -h` for help)

## API Endpoints

### Videos

- `GET /api/videos` - List all videos with pagination and filters
- `GET /api/videos/{id}` - Get video details
- `POST /api/videos` - Upload new video
- `DELETE /api/videos/{id}` - Delete video
- `PUT /api/videos/{id}/reprocess` - Trigger reprocessing

### Transcripts

- `GET /api/transcripts` - List all transcripts
- `GET /api/transcripts/{id}` - Get transcript details
- `POST /api/transcripts` - Create manual transcript
- `PUT /api/transcripts/{id}` - Update transcript
- `DELETE /api/transcripts/{id}` - Delete transcript
- `PUT /api/transcripts/{id}/summarize` - Trigger summarization for a transcript

### Summaries

- `GET /api/summaries` - List all summaries
- `GET /api/summaries/{id}` - Get summary details
- `PUT /api/summaries/{id}` - Update summary
- `DELETE /api/summaries/{id}` - Delete summary

### Jobs

- `GET /api/jobs/transcription` - List transcription jobs
- `GET /api/jobs/summarization` - List summarization jobs
- `GET /api/jobs/{id}` - Get job details

### Analytics

- `GET /api/analytics/overview` - Get overall statistics
- `GET /api/analytics/transcription` - Get transcription statistics
- `GET /api/analytics/summarization` - Get summarization statistics
- `GET /api/analytics/trends` - Get processing trends over time

## Database Schema

The database schema includes the following tables:

- **videos**: Stores video metadata and status
- **transcripts**: Stores transcripts with links to videos (optional)
- **summaries**: Stores summaries with links to transcripts
- **transcription_jobs**: Tracks transcription processing jobs
- **summarization_jobs**: Tracks summarization processing jobs

## Development

### Directory Structure

```
video-transcriber/
├── data/
│   ├── videos/         # Uploaded video files
│   ├── transcriptions/ # Generated transcription files
│   └── summaries/      # Generated summary files
├── migrations/         # Database migration scripts
├── src/
│   ├── api.py              # FastAPI endpoints
│   ├── database.py         # Database connection and utilities
│   ├── job_queue.py        # Job queue management
│   ├── main.py             # Main entry point
│   ├── models.py           # SQLAlchemy models
│   ├── processor.py        # Video processing utilities
│   ├── schemas.py          # Pydantic schemas
│   ├── summarizer.py       # Summarization utilities
│   ├── transcription_worker.py  # Transcription worker
│   ├── summarization_worker.py  # Summarization worker
│   ├── utils.py            # Utility functions
│   └── worker.py           # Worker entry point
├── docker-compose.yml  # Docker Compose configuration
├── Dockerfile          # Docker build configuration
└── requirements.txt    # Python dependencies
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
