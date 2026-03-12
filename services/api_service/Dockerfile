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
COPY services/api_service/requirements.lock /app/services/api_service/requirements.lock

# Install required packages
RUN pip install --no-cache-dir -U pip setuptools wheel

# Install locked dependencies, then install the backend package without re-resolving.
RUN pip install --no-cache-dir -r /app/services/api_service/requirements.lock
RUN pip install --no-cache-dir --no-deps "/app[api]"

# Create necessary directories
RUN mkdir -p /app/data/videos /app/data/transcriptions /app/data/summaries /app/data/translations /app/data/db

# Set working directory to the consolidated backend root
WORKDIR /app

# Run the canonical backend API entrypoint
CMD ["python", "-m", "backend.app.entrypoints.api"]
