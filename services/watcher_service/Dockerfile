FROM python:3.12.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy common code
COPY common /app/common

# Copy API service (needed by watcher)
COPY services/api_service /app/api_service

# Install required packages
RUN pip install --no-cache-dir -U pip setuptools wheel

# Copy watcher service
COPY services/watcher_service /app/watcher_service

RUN pip install --no-cache-dir -r /app/common/requirements.lock
RUN pip install --no-cache-dir -r /app/watcher_service/requirements.lock
RUN pip install --no-cache-dir --no-deps -e /app/common
RUN pip install --no-cache-dir --no-deps -e /app/watcher_service

# Create a .pth file to ensure the common package is in the Python path
RUN echo "/app" > $(python -c "import site; print(site.getsitepackages()[0])")/app.pth

# Create necessary directories
RUN mkdir -p /app/data/videos /app/data/transcriptions /app/data/summaries /app/data/db

# Set working directory to watcher service
WORKDIR /app/watcher_service

# Set Python path to include api_service
ENV PYTHONPATH=/app:$PYTHONPATH

# Run the watcher service
CMD ["python", "-m", "watcher.watcher"]
