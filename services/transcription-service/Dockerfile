FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy common code
COPY common /app/common

# Install transcription service
COPY services/transcription-service /app/transcription-service

# Install required packages
RUN pip install --no-cache-dir -U pip setuptools wheel

# Install common package first
RUN pip install --no-cache-dir -e /app/common

# Fix the dependency path in pyproject.toml to point to the correct location in container
RUN sed -i 's|file://../common|file:///app/common|g' /app/transcription-service/pyproject.toml

# Install PyTorch first with CPU-only index to avoid conflicts
RUN pip install --no-cache-dir torch==1.13.1 torchvision==0.14.1 torchaudio==0.13.1 --index-url https://download.pytorch.org/whl/cpu

# Install the transcription service with all dependencies
# This will install all dependencies defined in pyproject.toml including ml, audio, and whisper extras
RUN pip install --no-cache-dir -e "/app/transcription-service[all]"

# Create a .pth file to ensure the common package is in the Python path
RUN echo "/app" > $(python -c "import site; print(site.getsitepackages()[0])")/app.pth

# Create necessary directories
RUN mkdir -p /app/data/videos /app/data/transcriptions

# Set working directory to transcription service
WORKDIR /app/transcription-service

# Run the transcription service
CMD ["python", "-m", "transcription.main"]
