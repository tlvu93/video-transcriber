FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy common code
COPY common /app/common

# Copy API service (needed by watcher)
COPY services/api-service /app/api-service

# Install watcher dependencies
COPY services/watcher-service /app/watcher-service
RUN pip install --no-cache-dir -U pip setuptools wheel
RUN pip install --no-cache-dir watchdog requests pika==1.3.2
RUN pip install --no-cache-dir -r /app/common/requirements.txt
RUN pip install --no-cache-dir -e /app/common

# Fix the dependency path in pyproject.toml
RUN sed -i 's|file://../common|file:///app/common|g' /app/watcher-service/pyproject.toml

# Now install the watcher service
RUN pip install --no-cache-dir -e /app/watcher-service

# Create a .pth file to ensure the common package is in the Python path
RUN echo "/app" > $(python -c "import site; print(site.getsitepackages()[0])")/app.pth

# Create necessary directories
RUN mkdir -p /app/data/videos /app/data/transcriptions /app/data/summaries /app/data/db

# Set working directory to watcher service
WORKDIR /app/watcher-service

# Set Python path to include api-service
ENV PYTHONPATH=/app:$PYTHONPATH

# Run the watcher service
CMD ["python", "-m", "watcher.watcher"]
