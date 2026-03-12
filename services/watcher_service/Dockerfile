FROM python:3.13.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy backend package metadata and runtime code
COPY pyproject.toml /app/pyproject.toml
COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic
COPY backend /app/backend

# Install required packages
RUN pip install --no-cache-dir -U pip setuptools wheel

COPY services/watcher_service/requirements.lock /app/services/watcher_service/requirements.lock

RUN pip install --no-cache-dir -r /app/services/watcher_service/requirements.lock
RUN pip install --no-cache-dir --no-deps "/app[watcher]"

# Create necessary directories
RUN mkdir -p /app/data/videos /app/data/transcriptions /app/data/summaries /app/data/db

# Set working directory to the consolidated backend root
WORKDIR /app

# Set Python path to include the consolidated backend tree
ENV PYTHONPATH=/app:$PYTHONPATH

# Run the canonical backend watcher entrypoint
CMD ["python", "-m", "backend.app.entrypoints.watcher"]
