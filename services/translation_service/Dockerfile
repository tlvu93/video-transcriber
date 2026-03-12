FROM python:3.13.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install required packages
RUN pip install --no-cache-dir -U pip setuptools wheel

# Copy backend package metadata and runtime code
COPY pyproject.toml /app/pyproject.toml
COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic
COPY backend /app/backend
COPY services/translation_service/requirements.lock /app/services/translation_service/requirements.lock

RUN pip install --no-cache-dir -r /app/services/translation_service/requirements.lock
RUN pip install --no-cache-dir --no-deps "/app[translation]"

# Create necessary directories
RUN mkdir -p /app/data/translations

# Set working directory to the consolidated backend root
WORKDIR /app

# Run the canonical backend translation entrypoint
CMD ["python", "-m", "backend.app.entrypoints.translation_worker"]
