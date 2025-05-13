FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install common package
COPY common /app/common
RUN pip install -e /app/common

# Install transcription service
COPY transcription-service /app/transcription-service
RUN pip install -e /app/transcription-service

# Create necessary directories
RUN mkdir -p /app/data/videos /app/data/transcriptions

# Set working directory to transcription service
WORKDIR /app/transcription-service

# Run the transcription service
CMD ["python", "-m", "transcription.main"]
