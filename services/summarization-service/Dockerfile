FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install common package
COPY common /app/common
RUN pip install -e /app/common

# Install summarization service
COPY summarization-service /app/summarization-service
RUN pip install -e /app/summarization-service

# Create necessary directories
RUN mkdir -p /app/data/transcriptions /app/data/summaries

# Set working directory to summarization service
WORKDIR /app/summarization-service

# Run the summarization service
CMD ["python", "-m", "summarization.main"]
