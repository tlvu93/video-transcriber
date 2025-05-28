FROM python:3.12-slim

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
RUN pip install --no-cache-dir -U pip setuptools wheel tokenizers==0.21.1

# Copy common code
COPY common /app/common

# Install common package first
# RUN pip install --no-cache-dir -e /app/common

# Copy transcription service
COPY services/transcription-service /app/transcription-service

# Fix the dependency path in pyproject.toml to point to the correct location in container
# RUN sed -i 's|file://../common|file:///app/common|g' /app/transcription-service/pyproject.toml

# Install the transcription service with all dependencies from pyproject.toml
RUN pip install --no-cache-dir -e "/app/transcription-service"

# Create a .pth file to ensure the common package is in the Python path
RUN echo "/app" > $(python -c "import site; print(site.getsitepackages()[0])")/app.pth

# Create necessary directories and ensure proper permissions
RUN mkdir -p /app/data/videos /app/data/transcriptions && \
    chmod -R 777 /app/data

# Set working directory to transcription service
WORKDIR /app/transcription-service

# Run the transcription service
CMD ["python", "-m", "transcription.main"]
