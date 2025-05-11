FROM python:3.10-slim

# Install system dependencies including ffmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and migrations
COPY src/ /app/src/
COPY migrations/ /app/migrations/
COPY alembic.ini /app/

# Create necessary directories
RUN mkdir -p /app/data/videos /app/data/transcriptions /app/data/summaries /app/data/db

# Default command (will be overridden by docker-compose.yml)
CMD ["python", "src/main.py"]
