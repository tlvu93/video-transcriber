FROM python:3.13.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    cmake \
    python3-dev \
    pkg-config \
    libssl-dev \
    ffmpeg \
    && curl https://sh.rustup.rs -sSf | sh -s -- -y --default-toolchain 1.74.1 \
    && . "$HOME/.cargo/env" \
    && rustup install 1.67.0 \
    && rustup default 1.67.0 \
    && rm -rf /var/lib/apt/lists/*

# Ensure Rust is in PATH for all future layers
ENV PATH="/root/.cargo/bin:${PATH}"

# Upgrade pip and install build tools
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -U pip setuptools wheel

# Copy backend package metadata and runtime code
COPY pyproject.toml /app/pyproject.toml
COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic
COPY backend /app/backend
COPY services/transcription_service/requirements.lock /app/services/transcription_service/requirements.lock

RUN pip install --no-cache-dir -r /app/services/transcription_service/requirements.lock
RUN pip install --no-cache-dir --no-deps "/app[transcription]"

# Create necessary directories used by the worker runtime
RUN mkdir -p /app/data/videos /app/data/transcriptions

# Set working directory to the consolidated backend root
WORKDIR /app

# Run the canonical backend transcription entrypoint
CMD ["python", "-m", "backend.app.entrypoints.transcription_worker"]
