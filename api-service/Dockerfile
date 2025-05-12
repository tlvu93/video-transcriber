FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install common package
COPY common /app/common
RUN pip install -e /app/common

# Install API service
COPY api-service /app/api-service
RUN pip install -e /app/api-service

# Create necessary directories
RUN mkdir -p /app/data/videos /app/data/transcriptions /app/data/summaries /app/data/db

# Set working directory to API service
WORKDIR /app/api-service

# Run the API service
CMD ["python", "-m", "api.main"]
