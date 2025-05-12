FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install common package
COPY common /app/common
RUN pip install -e /app/common

# Copy API service (needed by watcher)
COPY api-service /app/api-service

# Install watcher dependencies
COPY watcher-service /app/watcher-service
RUN pip install watchdog

# Create necessary directories
RUN mkdir -p /app/data/videos /app/data/transcriptions /app/data/summaries /app/data/db

# Set working directory to watcher service
WORKDIR /app/watcher-service

# Set Python path to include api-service
ENV PYTHONPATH=/app:$PYTHONPATH

# Run the watcher service
CMD ["python", "-m", "watcher.watcher"]
