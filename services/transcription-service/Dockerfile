FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy common code
COPY common /app/common

# Install transcription service
COPY services/transcription-service /app/transcription-service

# Install required packages
RUN pip install --no-cache-dir -U pip setuptools wheel
RUN pip install --no-cache-dir pika==1.3.2
RUN pip install --no-cache-dir -r /app/common/requirements.txt
RUN pip install --no-cache-dir -e /app/common

# Fix the dependency path in pyproject.toml
RUN sed -i 's|file://../common|file:///app/common|g' /app/transcription-service/pyproject.toml

# Now install the transcription service
RUN pip install --no-cache-dir -e /app/transcription-service

# Create a .pth file to ensure the common package is in the Python path
RUN echo "/app" > $(python -c "import site; print(site.getsitepackages()[0])")/app.pth

# Create necessary directories
RUN mkdir -p /app/data/videos /app/data/transcriptions

# Set working directory to transcription service
WORKDIR /app/transcription-service

# Run the transcription service
CMD ["python", "-m", "transcription.main"]
