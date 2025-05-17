FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy API service
COPY api-service /app/api-service

# Install required packages
RUN pip install fastapi uvicorn sqlalchemy pydantic psycopg2-binary python-multipart

# Create necessary directories
RUN mkdir -p /app/data/videos /app/data/transcriptions /app/data/summaries /app/data/db

# Set working directory to API service
WORKDIR /app/api-service

# Run the API service
CMD ["python", "-m", "api.main"]
